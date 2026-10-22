// Original Majestic Creations native inspection and reviewed recipes, protocol version 1.
#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "Common/TcpSocketBuilder.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/Base64.h"
#include "ImageUtils.h"
#include "ImageCore.h"
#include "IImageWrapperModule.h"
#include "UnrealClient.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "Editor.h"
#include "Selection.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "Framework/Docking/TabManager.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "ToolMenus.h"
#include "Interfaces/IPluginManager.h"
#include "Styling/SlateStyle.h"
#include "Styling/SlateStyleRegistry.h"
#include "Brushes/SlateImageBrush.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBox.h"
#include "ForgeBlueprints.h"
#include "ForgeAssets.h"
#include "ForgeDataTables.h"
#include "ForgeCsvImport.h"
#include "ForgeStructTooltips.h"
#include "ForgeActors.h"
#include "ForgeLandscape.h"
#include "ForgeCollisionQueries.h"
#include "ForgeDirtyPackages.h"
#include "ForgeLevels.h"
#include "ForgeBlueprintEdits.h"
#include "ForgeMeshImport.h"
#include "ForgeMaterials.h"
#include "ForgeMaterialInstances.h"
#include "ForgeMeshExport.h"
#include "ForgeTransferPanel.h"
#include "Widgets/Layout/SScrollBox.h"
#include "SWebBrowser.h"
#include "ForgeWebBridge.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#include "Windows/AllowWindowsPlatformTypes.h"
#include <sddl.h>
#include <bcrypt.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogMajesticForge, Log, All);

class FMajesticForgeModule : public IModuleInterface
{
    // Keep aligned with server/core/connections.py MAX_REQUEST so bounded
    // 32,768-sample Landscape heightmap chunks can cross the native bridge.
    static constexpr int32 MaxRequestBytes = 512 * 1024;
    // Bounded requests and replies can span many editor ticks. Keep a finite
    // total lifetime while dropping stalled clients sooner.
    static constexpr double MaxClientLifetimeSeconds = 60.0;
    static constexpr double MaxClientIdleSeconds = 10.0;

    static FString PluginVersion()
    {
        const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("MajesticForge"));
        return Plugin.IsValid() ? Plugin->GetDescriptor().VersionName : TEXT("unknown");
    }

    struct FClient
    {
        FSocket* Socket = nullptr;
        TArray<uint8> Input;
        TArray<uint8> Output;
        int32 Sent = 0;
        double Started = FPlatformTime::Seconds();
        double LastActivity = FPlatformTime::Seconds();
        bool bScreenshotPending = false;
        uint64 ScreenshotRequestedFrame = 0;
    };
    FSocket* Listener = nullptr;
    TArray<FClient> Clients;
    FTSTicker::FDelegateHandle TickHandle;
    FString Token, SessionId, RegistrationPath;
    FString LastError;
    int32 Port = 0;
    bool bUIRegistered = false;
    double LastAuthenticatedRequest = 0;
    TWeakPtr<SDockTab> PanelTab;
    TSharedPtr<SWebBrowser> WebView;
    UForgeWebBridge* WebBridge = nullptr;
    TSharedPtr<FSlateStyleSet> LogoStyle;
    FForgeBlueprints BlueprintAutomation;
    FForgeActors ActorAutomation;
    FForgeLandscape LandscapeAutomation;
    FForgeCollisionQueries CollisionQueries;
    FForgeLevels LevelAutomation;
    FForgeBlueprintEdits BlueprintEdits;
    FForgeMeshImport MeshImporter;
    FForgeMaterials MaterialAutomation;
    FForgeMaterialInstances MaterialInstanceAutomation;
    FForgeMeshExport MeshExporter;
    FForgeTransferPanel TransferPanel;
    FForgeAssets AssetAutomation;
    FForgeDataTables DataTableAutomation;
    FForgeCsvImport CsvImporter;
    FForgeStructTooltips StructTooltips;

    bool IsForgeMcpConnected() const
    {
        return Listener && LastAuthenticatedRequest > 0 &&
            FPlatformTime::Seconds() - LastAuthenticatedRequest <= 6.0;
    }

    FText ConnectionStatusText() const
    {
        if (!Listener) return FText::FromString(TEXT("Not connected — bridge stopped."));
        if (LastAuthenticatedRequest == 0)
            return FText::FromString(TEXT("Not connected — waiting for the ForgeMCP client."));
        const double Age = FPlatformTime::Seconds() - LastAuthenticatedRequest;
        if (Age <= 6.0) return FText::FromString(TEXT("Connected to ForgeMCP."));
        return FText::FromString(FString::Printf(
            TEXT("Connection interrupted — last authenticated request: %.0f seconds ago."), Age));
    }

    FSlateColor ConnectionDotColor() const
    {
        if (!Listener || LastAuthenticatedRequest == 0)
            return FSlateColor(FLinearColor(0.95f, 0.08f, 0.08f, 1.0f));
        if (!IsForgeMcpConnected())
            return FSlateColor(FLinearColor(1.0f, 0.68f, 0.04f, 1.0f));

        // A gentle 1.2 Hz pulse makes a live authenticated heartbeat obvious.
        const float Pulse = 0.35f + 0.65f * (0.5f + 0.5f * FMath::Sin(
            static_cast<float>(FPlatformTime::Seconds() * 2.0 * PI * 1.2)));
        return FSlateColor(FLinearColor(0.06f * Pulse, 0.9f * Pulse, 0.16f * Pulse, 1.0f));
    }

    static bool ProtectSessionPath(const FString& Path)
    {
#if PLATFORM_WINDOWS
        PSECURITY_DESCRIPTOR Descriptor = nullptr;
        if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(
            L"D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)", SDDL_REVISION_1, &Descriptor, nullptr)) return false;
        const bool Protected = SetFileSecurityW(*FPaths::ConvertRelativePathToFull(Path),
            DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION, Descriptor) != 0;
        LocalFree(Descriptor);
        return Protected;
#else
        // This plugin package is Windows-only. Never expose unprotected credentials.
        return false;
#endif
    }

    static bool SecureToken(FString& OutToken)
    {
#if PLATFORM_WINDOWS
        uint8 Bytes[32];
        if (BCryptGenRandom(nullptr, Bytes, sizeof(Bytes), BCRYPT_USE_SYSTEM_PREFERRED_RNG) < 0) return false;
        OutToken = BytesToHex(Bytes, sizeof(Bytes)).ToLower();
        return true;
#else
        return false;
#endif
    }

    static FString SessionDirectory()
    {
        FString Override = FPlatformMisc::GetEnvironmentVariable(TEXT("FORGE_UNREAL_SESSION_DIR"));
        if (Override.IsEmpty()) Override = FPlatformMisc::GetEnvironmentVariable(TEXT("FORGE_SESSION_DIR"));
        if (!Override.IsEmpty()) return FPaths::ConvertRelativePathToFull(Override);
#if PLATFORM_WINDOWS
        const FString LocalAppData = FPlatformMisc::GetEnvironmentVariable(TEXT("LOCALAPPDATA"));
        if (!LocalAppData.IsEmpty())
        {
            return FPaths::Combine(LocalAppData, TEXT("MajesticForge"), TEXT("sessions"));
        }
#endif
        return FString();
    }

    bool TokenMatches(const FString& Candidate) const
    {
        if (Candidate.Len() != 64 || Token.Len() != 64) return false;
        uint32 Difference = 0;
        for (int32 Index = 0; Index < 64; ++Index) Difference |= Candidate[Index] ^ Token[Index];
        return Difference == 0;
    }

    static bool BoundedJson(const FString& Text)
    {
        int32 Depth = 0;
        bool InString = false, Escaped = false;
        for (TCHAR Character : Text)
        {
            if (InString)
            {
                if (Escaped) Escaped = false;
                else if (Character == '\\') Escaped = true;
                else if (Character == '"') InString = false;
            }
            else if (Character == '"') InString = true;
            else if (Character == '{' || Character == '[') { if (++Depth > 8) return false; }
            else if (Character == '}' || Character == ']') { if (--Depth < 0) return false; }
        }
        return Depth == 0 && !InString;
    }

    void RegisterMenus()
    {
        FToolMenuOwnerScoped Owner(this);
        UToolMenu* Menu = UToolMenus::Get()->ExtendMenu(TEXT("LevelEditor.MainMenu.Window"));
        Menu->FindOrAddSection(TEXT("MajesticForge")).AddMenuEntry(
            TEXT("OpenMajesticForge"), FText::FromString(TEXT("ForgeMCP")),
            FText::FromString(TEXT("Open the ForgeMCP connection panel.")), FSlateIcon(TEXT("ForgeMCPStyle"), TEXT("ForgeMCP.Logo")),
            FUIAction(FExecuteAction::CreateLambda([]()
            {
                FGlobalTabmanager::Get()->TryInvokeTab(FName(TEXT("MajesticForgeConnection")));
            })));
    }

    FString BuildUiState() const
    {
        TSharedRef<FJsonObject> State = MakeShared<FJsonObject>();
        const bool bConnected = IsForgeMcpConnected();
        const bool bInterrupted = Listener && LastAuthenticatedRequest > 0 && !bConnected;
        State->SetStringField(TEXT("version"), PluginVersion());
        State->SetBoolField(TEXT("bridge_running"), Listener != nullptr);
        State->SetBoolField(TEXT("connected"), bConnected);
        State->SetBoolField(TEXT("interrupted"), bInterrupted);
        State->SetStringField(TEXT("connection_text"), ConnectionStatusText().ToString());
        State->SetStringField(TEXT("endpoint"), Listener ? FString::Printf(TEXT("127.0.0.1:%d"), Port) : TEXT(""));
        State->SetStringField(TEXT("session_id"), SessionId);
        State->SetStringField(TEXT("project_name"), FApp::GetProjectName());
        State->SetStringField(TEXT("root"), TransferPanel.HandoffRoot());
        State->SetStringField(TEXT("blender_session"), TransferPanel.BlenderSessionId());
        State->SetStringField(TEXT("blender_object"), TransferPanel.BlenderObjectName());
        State->SetStringField(TEXT("destination"), TransferPanel.UnrealDestination());
        State->SetStringField(TEXT("object_name"), TransferPanel.UnrealObjectName());
        State->SetStringField(TEXT("format"), TransferPanel.ExportFormat());
        State->SetBoolField(TEXT("replace"), TransferPanel.ReplaceExisting());
        State->SetBoolField(TEXT("transfer_busy"), TransferPanel.Busy());
        State->SetBoolField(TEXT("transfer_applying"), TransferPanel.IsApplying());
        State->SetBoolField(TEXT("can_confirm"), TransferPanel.CanConfirm());
        State->SetStringField(TEXT("transfer_status"), TransferPanel.StatusText());
        return Json(State);
    }

    void DispatchUiAction(const FString& Action, const FString& Payload)
    {
        if (!IsInGameThread() || Payload.Len() > 8192) return;
        if (Action == TEXT("start")) { if (!Listener) StartBridge(); return; }
        if (Action == TEXT("stop")) { if (Listener && !TransferPanel.Busy()) StopBridge(); return; }
        if (Action == TEXT("configure"))
        {
            TSharedPtr<FJsonObject> Settings;
            if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Payload), Settings) || !Settings.IsValid()) return;
            FString Root, BlenderSession, BlenderObject, Destination, ObjectName, Format;
            Settings->TryGetStringField(TEXT("root"), Root);
            Settings->TryGetStringField(TEXT("blender_session"), BlenderSession);
            Settings->TryGetStringField(TEXT("blender_object"), BlenderObject);
            Settings->TryGetStringField(TEXT("destination"), Destination);
            Settings->TryGetStringField(TEXT("object_name"), ObjectName);
            Settings->TryGetStringField(TEXT("format"), Format);
            bool bReplace = false;
            Settings->TryGetBoolField(TEXT("replace"), bReplace);
            TransferPanel.Configure(Root, BlenderSession, BlenderObject, Destination, ObjectName, Format, bReplace);
            return;
        }
        if (!IsForgeMcpConnected()) return;
        if (Action == TEXT("send_to_blender")) TransferPanel.SendToBlender(SessionId);
        else if (Action == TEXT("send_to_unreal")) TransferPanel.SendToUnreal(SessionId);
        else if (Action == TEXT("confirm")) TransferPanel.Confirm();
        else if (Action == TEXT("cancel")) TransferPanel.Cancel();
    }

    TSharedRef<SDockTab> SpawnPanel(const FSpawnTabArgs&)
    {
        const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("MajesticForge"));
        const FString UiPath = Plugin.IsValid()
            ? FPaths::Combine(Plugin->GetBaseDir(), TEXT("Resources/ReactUI/index.html")) : FString();
        const bool bHasReactUi = !UiPath.IsEmpty() && FPaths::FileExists(UiPath);
        WebBridge = NewObject<UForgeWebBridge>();
        WebBridge->AddToRoot();
        WebBridge->Configure([this]() { return BuildUiState(); },
            [this](const FString& Action, const FString& Payload) { DispatchUiAction(Action, Payload); });
        FString UiUrl = FString::Printf(TEXT("file:///%s"), *FPaths::ConvertRelativePathToFull(UiPath));
        UiUrl.ReplaceInline(TEXT("\\"), TEXT("/"));
        UiUrl.ReplaceInline(TEXT("%"), TEXT("%25"));
        UiUrl.ReplaceInline(TEXT("#"), TEXT("%23"));
        UiUrl.ReplaceInline(TEXT(" "), TEXT("%20"));
        WebView = SNew(SWebBrowser)
            .InitialURL(bHasReactUi ? UiUrl : TEXT("about:blank"))
            .ShowAddressBar(false)
            .ShowErrorMessage(false)
            .SupportsTransparency(false)
            .SupportsThumbMouseButtonNavigation(false)
            .BrowserFrameRate(30);
        if (!bHasReactUi)
            WebView->LoadString(TEXT("<!doctype html><meta charset='utf-8'><body style='background:#111923;color:#fff;font:16px sans-serif;padding:24px'>ForgeMCP React UI is missing. Rebuild the web UI package.</body>"), TEXT("about:blank"));
        WebView->BindUObject(TEXT("forge"), WebBridge, true);
        TSharedRef<SDockTab> Tab = SNew(SDockTab).TabRole(ETabRole::NomadTab)
        .OnTabClosed_Lambda([this](TSharedRef<SDockTab>)
        {
            WebView.Reset();
            if (WebBridge)
            {
                WebBridge->RemoveFromRoot();
                WebBridge = nullptr;
            }
        })
        [ SNew(SBorder).Padding(0)[ WebView.ToSharedRef() ] ];
        PanelTab = Tab;
        return Tab;
    }

    static FString Json(const TSharedRef<FJsonObject>& Object)
    {
        FString Text;
        FJsonSerializer::Serialize(Object, TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));
        return Text;
    }

    void Destroy(FSocket*& Socket)
    {
        if (Socket)
        {
            Socket->Close();
            ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket);
            Socket = nullptr;
        }
    }

    TSharedRef<FJsonObject> Reply(const FString& Text, bool bAfterRenderedFrame, uint64 RequestedFrame, bool& bDeferScreenshot)
    {
        bDeferScreenshot = false;
        auto Result = MakeShared<FJsonObject>();
        auto Fail = [&](const FString& Code, const FString& Message)
        {
            Result->SetBoolField(TEXT("ok"), false);
            auto Error = MakeShared<FJsonObject>();
            Error->SetStringField(TEXT("code"), Code);
            Error->SetStringField(TEXT("message"), Message);
            Result->SetObjectField(TEXT("error"), Error);
            return Result;
        };
        TSharedPtr<FJsonObject> Request;
        if (!BoundedJson(Text) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Request) || !Request.IsValid())
            return Fail(TEXT("invalid_request"), TEXT("Expected one JSON object."));
        FString RequestId, SuppliedToken, Command;
        double Version = 0;
        Request->TryGetStringField(TEXT("request_id"), RequestId);
        Result->SetStringField(TEXT("request_id"), RequestId.Left(128));
        if (!Request->TryGetNumberField(TEXT("protocol_version"), Version) || Version != 1 || RequestId.IsEmpty() || RequestId.Len() > 128)
            return Fail(TEXT("invalid_request"), TEXT("Unsupported protocol or request identifier."));
        if (!Request->TryGetStringField(TEXT("token"), SuppliedToken) || !TokenMatches(SuppliedToken))
            return Fail(TEXT("unauthorized"), TEXT("Session authentication failed."));
        LastAuthenticatedRequest = FPlatformTime::Seconds();
        if (!Request->TryGetStringField(TEXT("command"), Command))
            return Fail(TEXT("invalid_request"), TEXT("Missing command."));
        const TSharedPtr<FJsonObject>* ValidatedArgs = nullptr;
        if (Request->HasField(TEXT("args")) && !Request->TryGetObjectField(TEXT("args"), ValidatedArgs))
            return Fail(TEXT("invalid_arguments"), TEXT("args must be an object."));

        auto Data = MakeShared<FJsonObject>();
        if (Command == TEXT("health"))
        {
            Data->SetStringField(TEXT("adapter"), TEXT("ForgeMCP Unreal"));
            Data->SetNumberField(TEXT("transfer_contract_version"), 1);
            Data->SetStringField(TEXT("version"), PluginVersion());
            Data->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
            Data->SetBoolField(TEXT("read_only"), false);
            Data->SetArrayField(TEXT("capabilities"), {MakeShared<FJsonValueString>(TEXT("blueprint_preview")),MakeShared<FJsonValueString>(TEXT("blueprint_apply")),MakeShared<FJsonValueString>(TEXT("blueprint_info")),MakeShared<FJsonValueString>(TEXT("class_info")),MakeShared<FJsonValueString>(TEXT("gas_info"))});
            auto Capabilities = Data->GetArrayField(TEXT("capabilities"));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("widget_tree_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("widget_hide_text")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_search")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("list_data_assets")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("list_data_asset_classes")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("data_asset_schema")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("data_asset_create_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("data_asset_create_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("data_asset_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("data_asset_edit_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("editor_log")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("capture_screenshot")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("editor_test_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("editor_test_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("editor_test_status")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("get_data_table_schema")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("get_data_table_rows")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("get_data_table_row")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("csv_import_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("csv_import_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("struct_tooltips_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("struct_tooltips_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("get_selected_assets")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("open_asset")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("sync_browser")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_property_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_property_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_property_edit_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("get_selected_actors")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("find_actors")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_components_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("component_property_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("component_property_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("component_property_edit_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_property_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_property_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_property_edit_apply")));
            for (const TCHAR* TerrainCommand : { TEXT("landscape_info"), TEXT("landscape_preview"), TEXT("landscape_apply"), TEXT("landscape_job_status"), TEXT("landscape_job_cancel") }) Capabilities.Add(MakeShared<FJsonValueString>(TerrainCommand));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("collision_query")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("inspect_dirty_packages")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_delete_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_delete_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("level_save_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("level_save_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("level_create_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("level_create_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("current_level_save_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("current_level_save_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("blueprint_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("blueprint_edit_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_import_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_import_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_replace_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_replace_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_graph_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_edit_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_instance_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_instance_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_instance_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_instance_save_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("material_instance_save_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_export_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_export_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("mesh_binding_info")));
            Data->SetArrayField(TEXT("capabilities"), Capabilities);
        }
        else if (Command == TEXT("editor_log"))
        {
            int32 Limit = 100;
            const TSharedPtr<FJsonObject>* Args = nullptr;
            if (Request->TryGetObjectField(TEXT("args"), Args) && (*Args)->HasField(TEXT("limit")))
            {
                double LimitNumber = 0;
                if (!(*Args)->TryGetNumberField(TEXT("limit"), LimitNumber) || LimitNumber < 1 || LimitNumber > 200 || FMath::FloorToDouble(LimitNumber) != LimitNumber)
                    return Fail(TEXT("invalid_arguments"), TEXT("limit must be an integer from 1 to 200."));
                Limit = static_cast<int32>(LimitNumber);
            }
            const FString EditorLogPath = FPaths::Combine(FPaths::ProjectLogDir(), FString(FApp::GetProjectName()) + TEXT(".log"));
            TUniquePtr<FArchive> Reader(IFileManager::Get().CreateFileReader(
                *EditorLogPath, FILEREAD_Silent | FILEREAD_AllowWrite));
            if (!Reader)
                return Fail(TEXT("log_unavailable"), TEXT("The active project's Unreal Editor log file is not available."));
            constexpr int64 MaxBytes = 131072;
            const int64 FileSize = Reader->TotalSize();
            const int64 ReadSize = FMath::Min(FileSize, MaxBytes);
            const int64 Start = FileSize - ReadSize;
            Reader->Seek(Start);
            TArray<uint8> Buffer;
            Buffer.SetNumUninitialized(ReadSize + 1);
            Reader->Serialize(Buffer.GetData(), ReadSize);
            Buffer[ReadSize] = 0;
            Reader.Reset();
            FString LogText;
            FFileHelper::BufferToString(LogText, Buffer.GetData(), static_cast<int32>(ReadSize));
            if (Start > 0)
            {
                const int32 FirstNewline = LogText.Find(TEXT("\n"));
                LogText = FirstNewline == INDEX_NONE ? FString() : LogText.Mid(FirstNewline + 1);
            }
            TArray<FString> Lines;
            LogText.ParseIntoArrayLines(Lines, false);
            const int32 First = FMath::Max(0, Lines.Num() - Limit);
            TArray<TSharedPtr<FJsonValue>> Results;
            for (int32 Index = First; Index < Lines.Num(); ++Index)
                Results.Add(MakeShared<FJsonValueString>(Lines[Index].Left(2048)));
            Data->SetArrayField(TEXT("lines"), Results);
            Data->SetNumberField(TEXT("total_returned"), Results.Num());
            Data->SetBoolField(TEXT("truncated"), Start > 0 || First > 0);
            Data->SetNumberField(TEXT("max_bytes_read"), MaxBytes);
        }
        else if (Command == TEXT("capture_screenshot"))
        {
            if (ValidatedArgs && (*ValidatedArgs)->Values.Num() != 0)
                return Fail(TEXT("invalid_arguments"), TEXT("capture_screenshot accepts no arguments."));
            // The first bridge tick can run before the viewport has rendered a
            // terrain edit made in that same tick. Hold this request for one
            // editor frame so ReadPixels observes the updated back buffer.
            if (!bAfterRenderedFrame)
            {
                bDeferScreenshot = true;
                return Result;
            }
            FViewport* Viewport = GEditor ? GEditor->GetActiveViewport() : nullptr;
            if (!Viewport)
                return Fail(TEXT("viewport_unavailable"), TEXT("No active Unreal Editor viewport is available."));

            const FIntPoint SourceSize = Viewport->GetSizeXY();
            constexpr int32 MaxSourceDimension = 8192;
            constexpr int64 MaxSourcePixels = 16777216;
            if (SourceSize.X < 1 || SourceSize.Y < 1 || SourceSize.X > MaxSourceDimension ||
                SourceSize.Y > MaxSourceDimension || static_cast<int64>(SourceSize.X) * SourceSize.Y > MaxSourcePixels)
                return Fail(TEXT("viewport_size_unsupported"), TEXT("The active viewport has unsupported dimensions."));

            TArray<FColor> SourcePixels;
            FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
            ReadFlags.SetLinearToGamma(true);
            if (!Viewport->ReadPixels(SourcePixels, ReadFlags) ||
                SourcePixels.Num() != SourceSize.X * SourceSize.Y)
                return Fail(TEXT("viewport_read_failed"), TEXT("Unreal could not read the active viewport pixels."));

            constexpr int32 MaxWidth = 1280;
            constexpr int32 MaxHeight = 720;
            const double Scale = FMath::Min(1.0, FMath::Min(
                static_cast<double>(MaxWidth) / SourceSize.X,
                static_cast<double>(MaxHeight) / SourceSize.Y));
            const int32 Width = FMath::Max(1, FMath::RoundToInt(SourceSize.X * Scale));
            const int32 Height = FMath::Max(1, FMath::RoundToInt(SourceSize.Y * Scale));
            TArray<FColor> Pixels;
            if (Width == SourceSize.X && Height == SourceSize.Y)
                Pixels = MoveTemp(SourcePixels);
            else
                FImageUtils::CropAndScaleImage(SourceSize.X, SourceSize.Y, Width, Height, SourcePixels, Pixels);
            if (Pixels.Num() != Width * Height)
                return Fail(TEXT("image_encode_failed"), TEXT("Unreal could not scale the viewport image in memory."));

            TArray64<uint8> Compressed;
            IImageWrapperModule& ImageWrapper = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
            if (!ImageWrapper.CompressImage(Compressed, EImageFormat::JPEG,
                FImageView(Pixels.GetData(), Width, Height, EGammaSpace::sRGB), 78) ||
                Compressed.IsEmpty() || Compressed.Num() > 700 * 1024)
                return Fail(TEXT("screenshot_too_large"), TEXT("The JPEG exceeded the safe bridge response limit."));

            Data->SetStringField(TEXT("mime_type"), TEXT("image/jpeg"));
            Data->SetStringField(TEXT("image_base64"), FBase64::Encode(Compressed.GetData(), Compressed.Num()));
            Data->SetNumberField(TEXT("width"), Width);
            Data->SetNumberField(TEXT("height"), Height);
            Data->SetNumberField(TEXT("source_width"), SourceSize.X);
            Data->SetNumberField(TEXT("source_height"), SourceSize.Y);
            Data->SetStringField(TEXT("capture_source"), TEXT("active_unreal_editor_viewport"));
            Data->SetNumberField(TEXT("capture_frame_number"), GFrameCounter);
            Data->SetNumberField(TEXT("rendered_frames_since_request"), GFrameCounter >= RequestedFrame ? GFrameCounter - RequestedFrame : 0);
            Data->SetBoolField(TEXT("window_resized"), false);
            Data->SetBoolField(TEXT("file_saved"), false);
        }
        else if (Command == TEXT("project_info") || Command == TEXT("list_actors") ||
            Command == TEXT("find_actors") || Command == TEXT("get_selected_actors"))
        {
            UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
            if (!World) return Fail(TEXT("editor_not_ready"), TEXT("No active editor world is available."));
            if (Command == TEXT("project_info"))
            {
                Data->SetStringField(TEXT("project_name"), FApp::GetProjectName());
                Data->SetStringField(TEXT("project_file"), FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()));
                Data->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
                Data->SetStringField(TEXT("level"), World->GetPathName());
                Data->SetBoolField(TEXT("play_in_editor"), GEditor->PlayWorld != nullptr);
            }
            else if (Command == TEXT("list_actors"))
            {
                double LimitNumber = 200;
                const TSharedPtr<FJsonObject>* Args = nullptr;
                if (Request->TryGetObjectField(TEXT("args"), Args) && (*Args)->HasField(TEXT("limit")))
                {
                    if (!(*Args)->TryGetNumberField(TEXT("limit"), LimitNumber) || LimitNumber < 1 || LimitNumber > 1000 || FMath::FloorToDouble(LimitNumber) != LimitNumber)
                        return Fail(TEXT("invalid_arguments"), TEXT("limit must be an integer from 1 to 1000."));
                }
                TArray<TSharedPtr<FJsonValue>> Actors;
                int32 Total = 0;
                for (TActorIterator<AActor> It(World); It; ++It)
                {
                    AActor* Actor = *It;
                    if (!IsValid(Actor)) continue;
                    ++Total;
                    if (Actors.Num() >= static_cast<int32>(LimitNumber)) continue;
                    auto Item = MakeShared<FJsonObject>();
                    Item->SetStringField(TEXT("id"), Actor->GetActorGuid().ToString());
                    Item->SetStringField(TEXT("name"), Actor->GetName());
                    Item->SetStringField(TEXT("label"), Actor->GetActorLabel());
                    Item->SetStringField(TEXT("class"), Actor->GetClass()->GetPathName());
                    Item->SetStringField(TEXT("path"), Actor->GetPathName());
                    Actors.Add(MakeShared<FJsonValueObject>(Item));
                }
                Data->SetArrayField(TEXT("actors"), Actors);
                Data->SetNumberField(TEXT("total_count"), Total);
                Data->SetBoolField(TEXT("truncated"), Total > Actors.Num());
                Data->SetStringField(TEXT("level"), World->GetPathName());
            }
            else if (Command == TEXT("find_actors"))
            {
                const TSharedPtr<FJsonObject>* Args = nullptr;
                const bool HasArgs = Request->TryGetObjectField(TEXT("args"), Args) && Args->IsValid();
                FString NameContains, ClassPath, TagName;
                double LimitNumber = 100, OffsetNumber = 0;
                bool HasName = false, HasClass = false, HasTag = false, IncludeTransform = false;
                if (HasArgs)
                {
                    const TSharedPtr<FJsonValue>* NameValue = (*Args)->Values.Find(TEXT("name_contains"));
                    const TSharedPtr<FJsonValue>* ClassValue = (*Args)->Values.Find(TEXT("class_path"));
                    const TSharedPtr<FJsonValue>* TagValue = (*Args)->Values.Find(TEXT("tag"));
                    const TSharedPtr<FJsonValue>* TransformValue = (*Args)->Values.Find(TEXT("include_transform"));
                    if (NameValue && NameValue->IsValid())
                    {
                        HasName = (*NameValue)->Type == EJson::String && (*NameValue)->TryGetString(NameContains) &&
                            !NameContains.IsEmpty() && NameContains.Len() <= 128;
                        if (!HasName) return Fail(TEXT("invalid_arguments"), TEXT("name_contains must be a nonempty string up to 128 characters."));
                    }
                    if (ClassValue && ClassValue->IsValid())
                    {
                        HasClass = (*ClassValue)->Type == EJson::String && (*ClassValue)->TryGetString(ClassPath) &&
                            !ClassPath.IsEmpty() && ClassPath.Len() <= 256;
                        if (!HasClass) return Fail(TEXT("invalid_arguments"), TEXT("class_path must be a nonempty exact class path up to 256 characters."));
                    }
                    if (TagValue && TagValue->IsValid())
                    {
                        HasTag = (*TagValue)->Type == EJson::String && (*TagValue)->TryGetString(TagName) &&
                            !TagName.IsEmpty() && TagName.Len() <= 128;
                        if (!HasTag) return Fail(TEXT("invalid_arguments"), TEXT("tag must be a nonempty exact actor tag up to 128 characters."));
                    }
                    if (TransformValue && TransformValue->IsValid())
                    {
                        if ((*TransformValue)->Type != EJson::Boolean || !(*TransformValue)->TryGetBool(IncludeTransform))
                            return Fail(TEXT("invalid_arguments"), TEXT("include_transform must be a boolean."));
                    }
                    for (const auto& Pair : (*Args)->Values)
                        if (Pair.Key != TEXT("name_contains") && Pair.Key != TEXT("class_path") &&
                            Pair.Key != TEXT("tag") && Pair.Key != TEXT("include_transform") &&
                            Pair.Key != TEXT("offset") && Pair.Key != TEXT("limit"))
                            return Fail(TEXT("invalid_arguments"), TEXT("Actor search contains an unsupported field."));
                    if ((*Args)->HasField(TEXT("limit")) &&
                        (!(*Args)->TryGetNumberField(TEXT("limit"), LimitNumber) ||
                         (*Args)->Values[TEXT("limit")]->Type != EJson::Number || LimitNumber < 1 ||
                         LimitNumber > 1000 || FMath::FloorToDouble(LimitNumber) != LimitNumber))
                        return Fail(TEXT("invalid_arguments"), TEXT("limit must be an integer from 1 to 1000."));
                    if ((*Args)->HasField(TEXT("offset")) &&
                        (!(*Args)->TryGetNumberField(TEXT("offset"), OffsetNumber) ||
                         (*Args)->Values[TEXT("offset")]->Type != EJson::Number || OffsetNumber < 0 ||
                         OffsetNumber > 1000000 || FMath::FloorToDouble(OffsetNumber) != OffsetNumber))
                        return Fail(TEXT("invalid_arguments"), TEXT("offset must be an integer from 0 to 1000000."));
                }
                if (!HasName && !HasClass && !HasTag)
                    return Fail(TEXT("invalid_arguments"), TEXT("Specify name_contains, class_path, tag, or one or more filters."));
                TArray<TSharedPtr<FJsonValue>> Actors;
                int32 TotalMatches = 0;
                for (TActorIterator<AActor> It(World); It; ++It)
                {
                    AActor* Actor = *It;
                    if (!IsValid(Actor)) continue;
                    const bool NameMatch = !HasName || Actor->GetName().Contains(NameContains, ESearchCase::IgnoreCase) ||
                        Actor->GetActorLabel().Contains(NameContains, ESearchCase::IgnoreCase);
                    const bool ClassMatch = !HasClass || Actor->GetClass()->GetPathName() == ClassPath;
                    const bool TagMatch = !HasTag || Actor->Tags.Contains(FName(*TagName));
                    if (!NameMatch || !ClassMatch || !TagMatch) continue;
                    if (TotalMatches >= static_cast<int32>(OffsetNumber) &&
                        Actors.Num() < static_cast<int32>(LimitNumber))
                    {
                        auto Item = MakeShared<FJsonObject>();
                        Item->SetStringField(TEXT("id"), Actor->GetActorGuid().ToString());
                        Item->SetStringField(TEXT("name"), Actor->GetName());
                        Item->SetStringField(TEXT("label"), Actor->GetActorLabel());
                        Item->SetStringField(TEXT("class"), Actor->GetClass()->GetPathName());
                        Item->SetStringField(TEXT("path"), Actor->GetPathName());
                        if (IncludeTransform)
                        {
                            auto AddVector = [&](const TCHAR* Field, const FVector& Vector)
                            {
                                Item->SetArrayField(Field, {MakeShared<FJsonValueNumber>(Vector.X),
                                    MakeShared<FJsonValueNumber>(Vector.Y), MakeShared<FJsonValueNumber>(Vector.Z)});
                            };
                            AddVector(TEXT("location"), Actor->GetActorLocation());
                            const FRotator Rotation = Actor->GetActorRotation();
                            AddVector(TEXT("rotation"), FVector(Rotation.Pitch, Rotation.Yaw, Rotation.Roll));
                            AddVector(TEXT("scale"), Actor->GetActorScale3D());
                        }
                        Actors.Add(MakeShared<FJsonValueObject>(Item));
                    }
                    ++TotalMatches;
                }
                const int32 Returned = Actors.Num();
                Data->SetArrayField(TEXT("actors"), Actors);
                Data->SetNumberField(TEXT("total_matches"), TotalMatches);
                Data->SetNumberField(TEXT("offset"), OffsetNumber);
                Data->SetNumberField(TEXT("returned_count"), Returned);
                Data->SetBoolField(TEXT("truncated"), OffsetNumber + Returned < TotalMatches);
                Data->SetStringField(TEXT("level"), World->GetPathName());
            }
            else
            {
                double LimitNumber = 100;
                const TSharedPtr<FJsonObject>* Args = nullptr;
                if (Request->TryGetObjectField(TEXT("args"), Args) && (*Args)->HasField(TEXT("limit")))
                {
                    if (!(*Args)->TryGetNumberField(TEXT("limit"), LimitNumber) || LimitNumber < 1 || LimitNumber > 200 || FMath::FloorToDouble(LimitNumber) != LimitNumber)
                        return Fail(TEXT("invalid_arguments"), TEXT("limit must be an integer from 1 to 200."));
                }
                TArray<TSharedPtr<FJsonValue>> Actors;
                USelection* Selection = GEditor ? GEditor->GetSelectedActors() : nullptr;
                TArray<AActor*> SelectedActors;
                if (Selection) Selection->GetSelectedObjects<AActor>(SelectedActors);
                const int32 Total = SelectedActors.Num();
                for (AActor* Actor : SelectedActors)
                {
                    if (!IsValid(Actor)) continue;
                    if (Actors.Num() >= static_cast<int32>(LimitNumber)) continue;
                    auto Item = MakeShared<FJsonObject>();
                    Item->SetStringField(TEXT("id"), Actor->GetActorGuid().ToString());
                    Item->SetStringField(TEXT("name"), Actor->GetName());
                    Item->SetStringField(TEXT("label"), Actor->GetActorLabel());
                    Item->SetStringField(TEXT("class"), Actor->GetClass()->GetPathName());
                    Item->SetStringField(TEXT("path"), Actor->GetPathName());
                    Actors.Add(MakeShared<FJsonValueObject>(Item));
                }
                Data->SetArrayField(TEXT("actors"), Actors);
                Data->SetNumberField(TEXT("total_count"), Total);
                Data->SetBoolField(TEXT("truncated"), Total > Actors.Num());
                Data->SetStringField(TEXT("level"), World->GetPathName());
            }
        }
        else if (Command == TEXT("asset_search") || Command == TEXT("list_data_assets") || Command == TEXT("list_data_asset_classes") ||
            Command == TEXT("data_asset_schema") || Command == TEXT("data_asset_create_preview") ||
            Command == TEXT("data_asset_create_apply") || Command == TEXT("data_asset_edit_preview") ||
            Command == TEXT("data_asset_edit_apply") ||
            Command == TEXT("asset_info") || Command == TEXT("get_selected_assets") ||
            Command == TEXT("open_asset") || Command == TEXT("sync_browser") || Command == TEXT("asset_property_info") ||
            Command == TEXT("asset_property_edit_preview") || Command == TEXT("asset_property_edit_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!AssetAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("get_data_table_schema") || Command == TEXT("get_data_table_rows") ||
            Command == TEXT("get_data_table_row"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!DataTableAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("csv_import_preview") || Command == TEXT("csv_import_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!CsvImporter.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("struct_tooltips_preview") || Command == TEXT("struct_tooltips_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!StructTooltips.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("level_save_preview") || Command == TEXT("level_save_apply") ||
            Command == TEXT("level_create_preview") || Command == TEXT("level_create_apply") ||
            Command == TEXT("current_level_save_preview") || Command == TEXT("current_level_save_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!LevelAutomation.Handle(Command, Args, Data, Code, Message, &LandscapeAutomation)) return Fail(Code, Message);
        }
        else if (Command == TEXT("landscape_info") || Command == TEXT("landscape_preview") || Command == TEXT("landscape_apply") || Command == TEXT("landscape_job_status") || Command == TEXT("landscape_job_cancel"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!LandscapeAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("collision_query"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!CollisionQueries.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("inspect_dirty_packages"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!ForgeDirtyPackages::Handle(Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("actor_info") || Command == TEXT("actor_components_info") || Command == TEXT("component_property_info") ||
            Command == TEXT("component_property_edit_preview") || Command == TEXT("component_property_edit_apply") || Command == TEXT("actor_property_info") ||
            Command == TEXT("actor_property_edit_preview") || Command == TEXT("actor_property_edit_apply") ||
            Command == TEXT("gas_info") || Command == TEXT("actor_preview") || Command == TEXT("actor_apply") ||
            Command == TEXT("actor_delete_preview") || Command == TEXT("actor_delete_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!ActorAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("blueprint_preview") || Command == TEXT("blueprint_apply") || Command == TEXT("blueprint_info") || Command == TEXT("class_info") ||
            Command == TEXT("editor_test_preview") || Command == TEXT("editor_test_apply") || Command == TEXT("editor_test_status"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!BlueprintAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("blueprint_edit_preview") || Command == TEXT("blueprint_edit_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!BlueprintEdits.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("mesh_import_preview") || Command == TEXT("mesh_import_apply") ||
            Command == TEXT("mesh_replace_preview") || Command == TEXT("mesh_replace_apply") || Command == TEXT("mesh_info"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!MeshImporter.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("mesh_export_preview") || Command == TEXT("mesh_export_apply") || Command == TEXT("mesh_binding_info"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!MeshExporter.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("material_graph_info") || Command == TEXT("material_preview") || Command == TEXT("material_apply") ||
            Command == TEXT("material_edit_preview") || Command == TEXT("material_edit_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!MaterialAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("material_instance_info") || Command == TEXT("material_instance_preview") ||
            Command == TEXT("material_instance_apply") || Command == TEXT("material_instance_save_preview") ||
            Command == TEXT("material_instance_save_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!MaterialInstanceAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else return Fail(TEXT("command_not_allowed"), TEXT("Command is not in the native allowlist."));
        Result->SetBoolField(TEXT("ok"), true);
        Result->SetObjectField(TEXT("data"), Data);
        return Result;
    }

    bool Tick(float)
    {
        // Editor/world inspection stays on the game thread; socket I/O never blocks.
        if (!IsInGameThread()) return true;
        TransferPanel.Tick();
        LandscapeAutomation.Tick();
        bool Pending = false;
        for (int32 Accepted = 0; Accepted < 16 && Clients.Num() < 16 && Listener->HasPendingConnection(Pending) && Pending; ++Accepted)
        {
            FSocket* Socket = Listener->Accept(TEXT("MajesticForgeClient"));
            if (!Socket) break;
            Socket->SetNonBlocking(true);
            FClient Client;
            Client.Socket = Socket;
            Clients.Add(MoveTemp(Client));
        }
        for (int32 Index = Clients.Num() - 1; Index >= 0; --Index)
        {
            FClient& Client = Clients[Index];
            const double Now = FPlatformTime::Seconds();
            bool Done = Now - Client.Started > MaxClientLifetimeSeconds ||
                Now - Client.LastActivity > MaxClientIdleSeconds;
            if (!Done && Client.Output.IsEmpty() && !Client.bScreenshotPending)
            {
                uint8 Buffer[4096];
                int32 Read = 0;
                if (Client.Socket->Recv(Buffer, sizeof(Buffer), Read) && Read > 0)
                {
                    Client.Input.Append(Buffer, Read);
                    Client.LastActivity = FPlatformTime::Seconds();
                }
                if (Client.Input.Num() > MaxRequestBytes) Done = true;
                int32 Newline = Client.Input.Find(static_cast<uint8>('\n'));
                if (!Done && Newline != INDEX_NONE)
                {
                    FUTF8ToTCHAR Converted(reinterpret_cast<const ANSICHAR*>(Client.Input.GetData()), Newline);
                    bool bDeferScreenshot = false;
                    const FString RequestText(Converted.Length(), Converted.Get());
                    TSharedRef<FJsonObject> ReplyObject = Reply(RequestText, false, 0, bDeferScreenshot);
                    Client.Started = Client.LastActivity = FPlatformTime::Seconds();
                    if (bDeferScreenshot)
                    {
                        Client.bScreenshotPending = true;
                        Client.ScreenshotRequestedFrame = GFrameCounter;
                    }
                    else
                    {
                        FString Response = Json(ReplyObject) + TEXT("\n");
                        FTCHARToUTF8 Encoded(*Response);
                        if (Encoded.Length() > 1024 * 1024) Done = true;
                        else Client.Output.Append(reinterpret_cast<const uint8*>(Encoded.Get()), Encoded.Length());
                    }
                }
            }
            else if (!Done && Client.bScreenshotPending && Client.Output.IsEmpty() &&
                GFrameCounter > Client.ScreenshotRequestedFrame)
            {
                const int32 Newline = Client.Input.Find(static_cast<uint8>('\n'));
                if (Newline == INDEX_NONE) Done = true;
                else
                {
                    FUTF8ToTCHAR Converted(reinterpret_cast<const ANSICHAR*>(Client.Input.GetData()), Newline);
                    bool bUnexpectedDefer = false;
                    const FString RequestText(Converted.Length(), Converted.Get());
                    FString Response = Json(Reply(RequestText, true, Client.ScreenshotRequestedFrame, bUnexpectedDefer)) + TEXT("\n");
                    Client.Started = Client.LastActivity = FPlatformTime::Seconds();
                    Client.bScreenshotPending = false;
                    FTCHARToUTF8 Encoded(*Response);
                    if (bUnexpectedDefer || Encoded.Length() > 1024 * 1024) Done = true;
                    else Client.Output.Append(reinterpret_cast<const uint8*>(Encoded.Get()), Encoded.Length());
                }
            }
            if (!Done && !Client.Output.IsEmpty())
            {
                int32 Written = 0;
                Client.Socket->Send(Client.Output.GetData() + Client.Sent, Client.Output.Num() - Client.Sent, Written);
                Client.Sent += Written;
                if (Written > 0) Client.LastActivity = FPlatformTime::Seconds();
                Done = Client.Sent >= Client.Output.Num();
            }
            if (Done)
            {
                Destroy(Client.Socket);
                Clients.RemoveAtSwap(Index);
            }
        }
        return true;
    }

    void StartBridge()
    {
        if (Listener) return;
        LastError.Empty();
        LastAuthenticatedRequest = 0;
        Listener = FTcpSocketBuilder(TEXT("MajesticForgeListener")).AsNonBlocking()
            .BoundToAddress(FIPv4Address(127, 0, 0, 1)).BoundToPort(0).Listening(16);
        if (!Listener)
        {
            UE_LOG(LogMajesticForge, Error, TEXT("Could not create loopback listener."));
            LastError = TEXT("Could not start the local listener. Check the editor log.");
            return;
        }
        auto Address = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
        Listener->GetAddress(*Address);
        Port = Address->GetPort();
        if (!SecureToken(Token))
        {
            LastError = TEXT("Secure token generation failed. Bridge remains stopped.");
            Destroy(Listener);
            return;
        }
        SessionId = FString::Printf(TEXT("unreal-%u"), FPlatformProcess::GetCurrentProcessId());
        FString Directory = SessionDirectory();
        if (Directory.IsEmpty())
        {
            LastError = TEXT("Could not locate the current user's local session folder. Bridge remains stopped.");
            Destroy(Listener);
            return;
        }
        IFileManager::Get().MakeDirectory(*Directory, true);
        if (!ProtectSessionPath(Directory))
        {
            LastError = TEXT("Could not protect the user-wide session folder. Bridge remains stopped.");
            Destroy(Listener);
            return;
        }
        RegistrationPath = FPaths::Combine(Directory, SessionId + TEXT(".json"));
        auto Registration = MakeShared<FJsonObject>();
        Registration->SetNumberField(TEXT("protocol_version"), 1);
        Registration->SetStringField(TEXT("session_id"), SessionId);
        Registration->SetStringField(TEXT("kind"), TEXT("unreal"));
        Registration->SetStringField(TEXT("host"), TEXT("127.0.0.1"));
        Registration->SetNumberField(TEXT("port"), Address->GetPort());
        Registration->SetNumberField(TEXT("pid"), FPlatformProcess::GetCurrentProcessId());
        Registration->SetStringField(TEXT("token"), Token);
        if (!FFileHelper::SaveStringToFile(Json(Registration), *RegistrationPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
            || !ProtectSessionPath(RegistrationPath))
        {
            UE_LOG(LogMajesticForge, Error, TEXT("Could not register local bridge session."));
            LastError = TEXT("Could not register the session. Check Saved folder access.");
            Destroy(Listener);
            IFileManager::Get().Delete(*RegistrationPath);
            return;
        }
        TickHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateRaw(this, &FMajesticForgeModule::Tick), 0.02f);
        UE_LOG(LogMajesticForge, Display, TEXT("Read-only local bridge ready (%s)."), *SessionId);
    }

    void StopBridge()
    {
        FTSTicker::RemoveTicker(TickHandle);
        for (auto& Client : Clients) Destroy(Client.Socket);
        Clients.Empty();
        Destroy(Listener);
        if (!RegistrationPath.IsEmpty()) IFileManager::Get().Delete(*RegistrationPath);
        RegistrationPath.Empty();
        Token.Empty();
        BlueprintAutomation.Reset();
        ActorAutomation.Reset();
        LandscapeAutomation.Reset();
        LevelAutomation.Reset();
        BlueprintEdits.Reset();
        MeshImporter.Reset();
        MaterialAutomation.Reset();
        MaterialInstanceAutomation.Reset();
        AssetAutomation.Reset();
        CsvImporter.Reset();
        StructTooltips.Reset();
        MaterialInstanceAutomation.Reset();
        MeshExporter.Reset();
        Port = 0;
        LastAuthenticatedRequest = 0;
    }

public:
    void StartupModule() override
    {
        if (IsRunningCommandlet()) return;
        LogoStyle = MakeShared<FSlateStyleSet>(TEXT("ForgeMCPStyle"));
        const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("MajesticForge"));
        if (Plugin.IsValid())
        {
            LogoStyle->Set(TEXT("ForgeMCP.Logo"), new FSlateImageBrush(
                FPaths::Combine(Plugin->GetBaseDir(), TEXT("Resources/Icon128.png")), FVector2D(128, 128)));
        }
        FSlateStyleRegistry::RegisterSlateStyle(*LogoStyle);
        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(FName(TEXT("MajesticForgeConnection")),
            FOnSpawnTab::CreateRaw(this, &FMajesticForgeModule::SpawnPanel))
            .SetDisplayName(FText::FromString(TEXT("ForgeMCP")))
            .SetIcon(FSlateIcon(TEXT("ForgeMCPStyle"), TEXT("ForgeMCP.Logo")))
            .SetMenuType(ETabSpawnerMenuType::Hidden);
        UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FMajesticForgeModule::RegisterMenus));
        bUIRegistered = true;
        StartBridge();
    }

    void ShutdownModule() override
    {
        if (bUIRegistered)
        {
            UToolMenus::UnRegisterStartupCallback(this);
            UToolMenus::UnregisterOwner(this);
            if (TSharedPtr<SDockTab> Tab = PanelTab.Pin()) Tab->RequestCloseTab();
            FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(FName(TEXT("MajesticForgeConnection")));
            bUIRegistered = false;
        }
        StopBridge();
        if (LogoStyle.IsValid())
        {
            FSlateStyleRegistry::UnRegisterSlateStyle(*LogoStyle);
            LogoStyle.Reset();
        }
    }
};

IMPLEMENT_MODULE(FMajesticForgeModule, MajesticForge)
