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
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Editor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "Misc/ConfigCacheIni.h"
#include "Framework/Docking/TabManager.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "ToolMenus.h"
#include "ForgeBlueprints.h"
#include "ForgeAssets.h"
#include "ForgeActors.h"
#include "ForgeBlueprintEdits.h"
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
    struct FClient
    {
        FSocket* Socket = nullptr;
        TArray<uint8> Input;
        TArray<uint8> Output;
        int32 Sent = 0;
        double Started = FPlatformTime::Seconds();
    };
    FSocket* Listener = nullptr;
    TArray<FClient> Clients;
    FTSTicker::FDelegateHandle TickHandle;
    FString Token, SessionId, RegistrationPath;
    FString LastError;
    int32 Port = 0;
    bool bAutoStart = true;
    bool bUIRegistered = false;
    double LastAuthenticatedRequest = 0;
    TWeakPtr<SDockTab> PanelTab;
    FForgeBlueprints BlueprintAutomation;
    FForgeActors ActorAutomation;
    FForgeBlueprintEdits BlueprintEdits;

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
            FText::FromString(TEXT("Open the ForgeMCP connection panel.")), FSlateIcon(),
            FUIAction(FExecuteAction::CreateLambda([]()
            {
                FGlobalTabmanager::Get()->TryInvokeTab(FName(TEXT("MajesticForgeConnection")));
            })));
    }

    TSharedRef<SDockTab> SpawnPanel(const FSpawnTabArgs&)
    {
        TSharedRef<SDockTab> Tab = SNew(SDockTab).TabRole(ETabRole::NomadTab)
        [
            SNew(SBorder).Padding(16)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 12)
                [ SNew(STextBlock).Text(FText::FromString(TEXT("ForgeMCP 0.2.0"))) ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 8)
                [ SNew(STextBlock).Text_Lambda([this]()
                    { return FText::FromString(Listener ? TEXT("Bridge running") : TEXT("Bridge stopped")); }) ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 8)
                [ SNew(STextBlock).Text_Lambda([this]()
                    { return FText::FromString(Listener ? FString::Printf(TEXT("127.0.0.1:%d  |  Session: %s"), Port, *SessionId) : LastError); }) ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 8)
                [ SNew(STextBlock).Text_Lambda([this]()
                    {
                        return FText::FromString(!Listener ? TEXT("Start the bridge to allow ForgeMCP inspection.") :
                            LastAuthenticatedRequest == 0 ? TEXT("Waiting for an authenticated request") :
                            FString::Printf(TEXT("Last authenticated request: %.0f seconds ago"), FPlatformTime::Seconds() - LastAuthenticatedRequest));
                    }) ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 12)
                [ SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
                    [ SNew(SButton).Text(FText::FromString(TEXT("Start Bridge")))
                        .IsEnabled_Lambda([this]() { return Listener == nullptr; })
                        .OnClicked_Lambda([this]() { StartBridge(); return FReply::Handled(); }) ]
                    + SHorizontalBox::Slot().AutoWidth()
                    [ SNew(SButton).Text(FText::FromString(TEXT("Stop Bridge")))
                        .IsEnabled_Lambda([this]() { return Listener != nullptr; })
                        .OnClicked_Lambda([this]() { StopBridge(); return FReply::Handled(); }) ]
                ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 12)
                [ SNew(SCheckBox).IsChecked_Lambda([this]()
                    { return bAutoStart ? ECheckBoxState::Checked : ECheckBoxState::Unchecked; })
                    .OnCheckStateChanged_Lambda([this](ECheckBoxState State)
                    {
                        bAutoStart = State == ECheckBoxState::Checked;
                        GConfig->SetBool(TEXT("MajesticForge"), TEXT("AutoStart"), bAutoStart, GEditorPerProjectIni);
                        GConfig->Flush(false, GEditorPerProjectIni);
                    })
                    [ SNew(STextBlock).Text(FText::FromString(TEXT("Start bridge when this project opens"))) ] ]
                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 8)
                [ SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("Project: %s"), FApp::GetProjectName()))) ]
                + SVerticalBox::Slot().AutoHeight()
                [ SNew(STextBlock).AutoWrapText(true).Text(FText::FromString(TEXT("Native Blueprint recipes require a reviewed preview. Connection controls do not modify assets."))) ]
            ]
        ];
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

    TSharedRef<FJsonObject> Reply(const FString& Text)
    {
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
            Data->SetStringField(TEXT("version"), TEXT("0.2.0"));
            Data->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
            Data->SetBoolField(TEXT("read_only"), false);
            Data->SetArrayField(TEXT("capabilities"), {MakeShared<FJsonValueString>(TEXT("blueprint_preview")),MakeShared<FJsonValueString>(TEXT("blueprint_apply")),MakeShared<FJsonValueString>(TEXT("blueprint_info")),MakeShared<FJsonValueString>(TEXT("class_info")),MakeShared<FJsonValueString>(TEXT("gas_info"))});
            auto Capabilities = Data->GetArrayField(TEXT("capabilities"));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_search")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("asset_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_info")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("actor_apply")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("blueprint_edit_preview")));
            Capabilities.Add(MakeShared<FJsonValueString>(TEXT("blueprint_edit_apply")));
            Data->SetArrayField(TEXT("capabilities"), Capabilities);
        }
        else if (Command == TEXT("project_info") || Command == TEXT("list_actors"))
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
            else
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
        }
        else if (Command == TEXT("asset_search") || Command == TEXT("asset_info"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!FForgeAssets::Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("actor_info") || Command == TEXT("gas_info") || Command == TEXT("actor_preview") || Command == TEXT("actor_apply"))
        {
            FString Code, Message;
            auto Args = ValidatedArgs ? ValidatedArgs->ToSharedRef() : MakeShared<FJsonObject>();
            if (!ActorAutomation.Handle(Command, Args, Data, Code, Message)) return Fail(Code, Message);
        }
        else if (Command == TEXT("blueprint_preview") || Command == TEXT("blueprint_apply") || Command == TEXT("blueprint_info") || Command == TEXT("class_info"))
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
        else return Fail(TEXT("command_not_allowed"), TEXT("Command is not in the native allowlist."));
        Result->SetBoolField(TEXT("ok"), true);
        Result->SetObjectField(TEXT("data"), Data);
        return Result;
    }

    bool Tick(float)
    {
        // Editor/world inspection stays on the game thread; socket I/O never blocks.
        if (!IsInGameThread()) return true;
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
            bool Done = FPlatformTime::Seconds() - Client.Started > 10;
            if (!Done && Client.Output.IsEmpty())
            {
                uint8 Buffer[4096];
                int32 Read = 0;
                if (Client.Socket->Recv(Buffer, sizeof(Buffer), Read) && Read > 0)
                    Client.Input.Append(Buffer, Read);
                if (Client.Input.Num() > 16384) Done = true;
                int32 Newline = Client.Input.Find(static_cast<uint8>('\n'));
                if (!Done && Newline != INDEX_NONE)
                {
                    FUTF8ToTCHAR Converted(reinterpret_cast<const ANSICHAR*>(Client.Input.GetData()), Newline);
                    FString Response = Json(Reply(FString(Converted.Length(), Converted.Get()))) + TEXT("\n");
                    Client.Started = FPlatformTime::Seconds();
                    FTCHARToUTF8 Encoded(*Response);
                    if (Encoded.Length() > 1024 * 1024) Done = true;
                    else Client.Output.Append(reinterpret_cast<const uint8*>(Encoded.Get()), Encoded.Length());
                }
            }
            if (!Done && !Client.Output.IsEmpty())
            {
                int32 Written = 0;
                Client.Socket->Send(Client.Output.GetData() + Client.Sent, Client.Output.Num() - Client.Sent, Written);
                Client.Sent += Written;
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
        FString Directory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("MajesticForge"));
        IFileManager::Get().MakeDirectory(*Directory, true);
        if (!ProtectSessionPath(Directory))
        {
            LastError = TEXT("Could not protect session credentials. Bridge remains stopped.");
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
        BlueprintEdits.Reset();
        Port = 0;
        LastAuthenticatedRequest = 0;
    }

public:
    void StartupModule() override
    {
        if (IsRunningCommandlet()) return;
        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(FName(TEXT("MajesticForgeConnection")),
            FOnSpawnTab::CreateRaw(this, &FMajesticForgeModule::SpawnPanel))
            .SetDisplayName(FText::FromString(TEXT("ForgeMCP")))
            .SetMenuType(ETabSpawnerMenuType::Hidden);
        UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FMajesticForgeModule::RegisterMenus));
        bUIRegistered = true;
        GConfig->GetBool(TEXT("MajesticForge"), TEXT("AutoStart"), bAutoStart, GEditorPerProjectIni);
        if (bAutoStart) StartBridge();
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
    }
};

IMPLEMENT_MODULE(FMajesticForgeModule, MajesticForge)
