#include "ForgeTransferPanel.h"
#include "ContentBrowserModule.h"
#include "IContentBrowserSingleton.h"
#include "AssetRegistry/AssetData.h"
#include "Editor.h"
#include "Engine/Selection.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Dom/JsonObject.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SCheckBox.h"

namespace
{
FString Json(const TSharedRef<FJsonObject>& O)
{
    FString S; FJsonSerializer::Serialize(O,TJsonWriterFactory<>::Create(&S));
    // Pipe messages are one JSON value per line.
    S.ReplaceInline(TEXT("\r"),TEXT("")); S.ReplaceInline(TEXT("\n"),TEXT("")); return S;
}
}
void FForgeTransferPanel::Close()
{
    if (Process.IsValid())
    {
        // Cancellation is an invalid approval, allowing the worker to close its MCP child.
        // Never kill an apply or replay it after an uncertain outcome.
        if (!bApplying && Write && FPlatformProcess::IsProcRunning(Process)) FPlatformProcess::WritePipe(Write,TEXT("{}"));
        FPlatformProcess::CloseProc(Process); Process.Reset();
    }
    FPlatformProcess::ClosePipe(Read,ChildWrite); FPlatformProcess::ClosePipe(ChildRead,Write);
    Read=ChildWrite=ChildRead=Write=nullptr; PreviewId.Empty(); Buffer.Empty(); bApplying=false;
}
FForgeTransferPanel::~FForgeTransferPanel() { Close(); }
void FForgeTransferPanel::Configure(const FString& InRoot, const FString& InBlenderSession,
    const FString& InBlenderObject, const FString& InDestination, const FString& InObjectName,
    const FString& InFormat, bool bInReplace)
{
    if (Busy()) return;
    if (ExportFormats.Num() == 0)
    {
        ExportFormats.Add(MakeShared<FString>(TEXT("fbx")));
        ExportFormats.Add(MakeShared<FString>(TEXT("obj")));
    }
    Root = InRoot.Left(1024);
    BlenderSession = InBlenderSession.Left(128);
    BlenderObject = InBlenderObject.Left(256);
    Destination = InDestination.Left(512);
    ObjectName = InObjectName.Left(256);
    bReplaceExisting = bInReplace;
    const FString NormalizedFormat = InFormat.ToLower();
    const FString SafeFormat = NormalizedFormat == TEXT("obj") ? TEXT("obj") : TEXT("fbx");
    for (const TSharedPtr<FString>& Candidate : ExportFormats)
        if (Candidate.IsValid() && *Candidate == SafeFormat) SelectedExportFormat = Candidate;
}
void FForgeTransferPanel::SendToBlender(const FString& UnrealSession)
{
    Begin(true, UnrealSession, ExportFormat());
}
void FForgeTransferPanel::SendToUnreal(const FString& UnrealSession)
{
    Begin(false, UnrealSession);
}
void FForgeTransferPanel::Confirm()
{
    if (!CanConfirm() || !Write) return;
    auto O = MakeShared<FJsonObject>();
    O->SetStringField(TEXT("confirmation"), PreviewId);
    bApplying = true;
    FPlatformProcess::WritePipe(Write, Json(O));
}
void FForgeTransferPanel::Cancel()
{
    if (!Busy() || bApplying) return;
    Close();
    Status = TEXT("Preview cancelled; no transfer applied.");
}
void FForgeTransferPanel::Begin(bool Send, const FString& Session, const FString& Format)
{
    if (Busy() || Session.IsEmpty() || !GEditor || GEditor->PlayWorld) return;
    FString Folder=FPaths::ConvertRelativePathToFull(Root);
    FString Python=FPaths::Combine(Folder,TEXT(".venv/Scripts/python.exe"));
    if (Folder.Contains(TEXT("\"")) || !FPaths::FileExists(Python) || !FPaths::FileExists(FPaths::Combine(Folder,TEXT("server/ui_transfer.py"))))
    { Status=TEXT("Choose the ForgeMCP folder containing its Python environment."); return; }
    auto Intent=MakeShared<FJsonObject>();
    Intent->SetStringField(TEXT("unreal_project_file"),FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()));
    if (Send)
    {
        UStaticMesh* Mesh=nullptr; TArray<FAssetData> Assets;
        FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser")).Get().GetSelectedAssets(Assets);
        if (Assets.Num()==1) Mesh=Cast<UStaticMesh>(Assets[0].GetAsset());
        if (!Mesh && GEditor->GetSelectedActors()->Num()==1)
            if (auto* Actor=Cast<AStaticMeshActor>(GEditor->GetSelectedActors()->GetSelectedObject(0))) Mesh=Actor->GetStaticMeshComponent()->GetStaticMesh();
        if (!Mesh) { Status=TEXT("Select exactly one static mesh asset or StaticMeshActor."); return; }
        Intent->SetStringField(TEXT("mode"),TEXT("send_to_blender"));
        Intent->SetStringField(TEXT("source_session_id"),Session);
        Intent->SetStringField(TEXT("target_session_id"),BlenderSession);
        Intent->SetStringField(TEXT("source_asset_path"),Mesh->GetPathName());
        Intent->SetStringField(TEXT("target_object"),ObjectName);
        Intent->SetStringField(TEXT("format"),Format);
    }
    else
    {
        Intent->SetStringField(TEXT("mode"),TEXT("import_from_blender"));
        Intent->SetStringField(TEXT("target_session_id"),Session);
        Intent->SetStringField(TEXT("source_session_id"),BlenderSession);
        Intent->SetStringField(TEXT("source_object"),BlenderObject);
        Intent->SetStringField(TEXT("target_asset_path"),Destination);
        Intent->SetBoolField(TEXT("save_assets"),true); Intent->SetBoolField(TEXT("place"),false);
        Intent->SetBoolField(TEXT("replace_existing"),bReplaceExisting);
    }
    if (!FPlatformProcess::CreatePipe(Read,ChildWrite) || !FPlatformProcess::CreatePipe(ChildRead,Write,true))
    { Close(); Status=TEXT("Cannot create transfer worker pipes."); return; }
    Process=FPlatformProcess::CreateProc(*Python,TEXT("-m server.ui_transfer"),false,true,true,nullptr,0,*Folder,ChildWrite,ChildRead);
    if (!Process.IsValid()) { Close(); Status=TEXT("Cannot start the transfer worker."); return; }
    FPlatformProcess::WritePipe(Write,Json(Intent));
    Started=FPlatformTime::Seconds(); Status=TEXT("Inspecting source and destination...");
}
void FForgeTransferPanel::Tick()
{
    if (!Busy()) return;
    Buffer+=FPlatformProcess::ReadPipe(Read);
    if (Buffer.Len()>1024*1024) { Status=TEXT("Worker response exceeded limits; inspect receipt."); Close(); return; }
    int32 End;
    while (Buffer.FindChar('\n',End))
    {
        FString Line=Buffer.Left(End); Buffer.RightChopInline(End+1);
        TSharedPtr<FJsonObject> O;
        if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Line),O) || !O.IsValid()) continue;
        FString State; if (!O->TryGetStringField(TEXT("state"),State)) continue;
        if (State==TEXT("preview"))
        {
            const auto P=O->GetObjectField(TEXT("preview")); PreviewId=P->GetStringField(TEXT("preview_id"));
            const auto Changes=P->GetObjectField(TEXT("changes"));
            FString Source, Target, SourceSession, TargetSession, Format=TEXT("fbx");
            Changes->TryGetStringField(TEXT("source_asset_path"),Source);
            if (Source.IsEmpty()) Changes->TryGetStringField(TEXT("source_object"),Source);
            Changes->TryGetStringField(TEXT("target_object"),Target);
            if (Target.IsEmpty()) Changes->TryGetStringField(TEXT("target_asset_path"),Target);
            Changes->TryGetStringField(TEXT("source_session_id"),SourceSession);
            Changes->TryGetStringField(TEXT("target_session_id"),TargetSession);
            Changes->TryGetStringField(TEXT("format"),Format);
            bool ReplaceExisting=false; Changes->TryGetBoolField(TEXT("replace_existing"),ReplaceExisting);
            if (ReplaceExisting)
            {
                FString Backup;
                if (P->HasField(TEXT("replacement")))
                    P->GetObjectField(TEXT("replacement"))->TryGetStringField(TEXT("backup_directory"),Backup);
                Status=FString::Printf(TEXT("Review replacement (%s):\nSource: %s (%s)\nExisting mesh: %s (%s)\nOnly a Blender-side edit is eligible; Unreal changes or binding conflicts are rejected.\nUnreal material assignments are preserved. Blender material edits are not applied.\nA verified package backup is retained at: %s\nConfirm within five minutes."),*Format,*Source,*SourceSession,*Target,*TargetSession,*Backup);
            }
            else
            {
                const FString FormatNote=Format==TEXT("obj") ? TEXT("OBJ carries triangulated geometry and UV0; normals and materials are not included. Unreal centimeters convert to Blender meters.") : TEXT("FBX carries the supported static mesh geometry and editable material placeholders.");
                Status=FString::Printf(TEXT("Review transfer (%s):\nSource: %s (%s)\nDestination: %s (%s)\nCreates a new destination; no overwrite.\nBlender file and Unreal level stay unsaved.\n%s\nConfirm within five minutes."),*Format,*Source,*SourceSession,*Target,*TargetSession,*FormatNote);
            }
        }
        else if (State==TEXT("applying")) { bApplying=true; Status=TEXT("Transferring. Keep both applications open."); }
        else
        {
            FString Receipt; O->TryGetStringField(TEXT("operation_id"),Receipt);
            Status=TEXT("Transfer ")+State+TEXT(". Receipt: ")+Receipt;
            if (O->HasField(TEXT("error"))) Status+=TEXT("\n")+Json(O->GetObjectField(TEXT("error")).ToSharedRef());
            if (O->HasField(TEXT("result")))
            {
                const auto Result=O->GetObjectField(TEXT("result"));
                if (Result->HasField(TEXT("data")))
                {
                    FString Diagnostic; Result->GetObjectField(TEXT("data"))->TryGetStringField(TEXT("diagnostic_code"),Diagnostic);
                    if (!Diagnostic.IsEmpty()) Status+=TEXT("\nDiagnostic: ")+Diagnostic;
                }
                if (Result->HasField(TEXT("error"))) Status+=TEXT("\n")+Json(Result->GetObjectField(TEXT("error")).ToSharedRef());
            }
            bApplying=false; Close(); return;
        }
    }
    if (!FPlatformProcess::IsProcRunning(Process) || FPlatformTime::Seconds()-Started>600)
    { Status=bApplying ? TEXT("Outcome uncertain. Inspect the receipt before retrying.") : TEXT("Worker stopped or preview expired."); Close(); }
}
TSharedRef<SWidget> FForgeTransferPanel::Widget(TFunction<FString()> Session)
{
    if (ExportFormats.Num() == 0)
    {
        ExportFormats.Add(MakeShared<FString>(TEXT("fbx")));
        ExportFormats.Add(MakeShared<FString>(TEXT("obj")));
    }
    if (!SelectedExportFormat.IsValid()) SelectedExportFormat=ExportFormats[0];
    return SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(0,12,0,4)
        [SNew(STextBlock).Text(FText::FromString(TEXT("Unreal / Blender handoff (static mesh FBX or OBJ)")))]
        + SVerticalBox::Slot().AutoHeight()[SNew(SEditableTextBox).Text(FText::FromString(Root)).HintText(FText::FromString(TEXT("ForgeMCP folder"))).IsEnabled_Lambda([this](){return !Busy();}).OnTextChanged_Lambda([this](const FText& T){Root=T.ToString();})]
        + SVerticalBox::Slot().AutoHeight()[SNew(SEditableTextBox).HintText(FText::FromString(TEXT("Blender session ID (blank if only one connected)"))).IsEnabled_Lambda([this](){return !Busy();}).OnTextChanged_Lambda([this](const FText& T){BlenderSession=T.ToString();})]
        + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("Blender object name (optional override):")))]
        + SVerticalBox::Slot().AutoHeight()[SNew(SEditableTextBox).HintText(FText::FromString(TEXT("Leave blank to keep the Unreal source name"))).IsEnabled_Lambda([this](){return !Busy();}).OnTextChanged_Lambda([this](const FText& T){ObjectName=T.ToString();})]
        + SVerticalBox::Slot().AutoHeight().Padding(0,4)[SNew(STextBlock).Text(FText::FromString(TEXT("Export format:")))]
        + SVerticalBox::Slot().AutoHeight()[SNew(SComboBox<TSharedPtr<FString>>).OptionsSource(&ExportFormats).InitiallySelectedItem(SelectedExportFormat).IsEnabled_Lambda([this](){return !Busy();})
            .OnGenerateWidget_Lambda([](TSharedPtr<FString> Item){return SNew(STextBlock).Text(FText::FromString(Item.IsValid()?*Item:TEXT("fbx")));})
            .OnSelectionChanged_Lambda([this](TSharedPtr<FString> Item,ESelectInfo::Type){if(Item.IsValid())SelectedExportFormat=Item;})
            [SNew(STextBlock).Text_Lambda([this](){return FText::FromString(SelectedExportFormat.IsValid()?*SelectedExportFormat:TEXT("fbx"));})]]
        + SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("Send to Blender"))).IsEnabled_Lambda([this,Session](){return !Busy()&&!Session().IsEmpty();}).OnClicked_Lambda([this,Session](){Begin(true,Session(),SelectedExportFormat.IsValid()?*SelectedExportFormat:TEXT("fbx"));return FReply::Handled();})]
        + SVerticalBox::Slot().AutoHeight()[SNew(SEditableTextBox).HintText(FText::FromString(TEXT("Blender source object (blank for active mesh)"))).IsEnabled_Lambda([this](){return !Busy();}).OnTextChanged_Lambda([this](const FText& T){BlenderObject=T.ToString();})]
        + SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("Unreal destination folder (source name retained):")))]
        + SVerticalBox::Slot().AutoHeight()[SNew(SEditableTextBox).Text(FText::FromString(Destination)).HintText(FText::FromString(TEXT("/Game/Content/Returns/"))).IsEnabled_Lambda([this](){return !Busy();}).OnTextChanged_Lambda([this](const FText& T){Destination=T.ToString();})]
        + SVerticalBox::Slot().AutoHeight().Padding(0,4)[SNew(SCheckBox).IsEnabled_Lambda([this](){return !Busy();})
            .IsChecked_Lambda([this](){return bReplaceExisting?ECheckBoxState::Checked:ECheckBoxState::Unchecked;})
            .OnCheckStateChanged_Lambda([this](ECheckBoxState State){bReplaceExisting=State==ECheckBoxState::Checked;})
            [SNew(STextBlock).Text(FText::FromString(TEXT("Replace matching bound mesh (verified backup required)")))]]
        + SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("Send to Unreal (from Blender)"))).IsEnabled_Lambda([this,Session](){return !Busy()&&!Session().IsEmpty();}).OnClicked_Lambda([this,Session](){Begin(false,Session());return FReply::Handled();})]
        + SVerticalBox::Slot().AutoHeight().Padding(0,8)[SNew(STextBlock).AutoWrapText(true).Text_Lambda([this](){return FText::FromString(Status);})]
        + SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("Confirm Transfer"))).IsEnabled_Lambda([this](){return Busy()&&!PreviewId.IsEmpty()&&!bApplying;}).OnClicked_Lambda([this](){auto O=MakeShared<FJsonObject>(); O->SetStringField(TEXT("confirmation"),PreviewId); bApplying=true; FPlatformProcess::WritePipe(Write,Json(O));return FReply::Handled();})]
        + SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("Cancel Preview"))).IsEnabled_Lambda([this](){return Busy()&&!bApplying;}).OnClicked_Lambda([this](){Close();Status=TEXT("Preview cancelled; no transfer applied.");return FReply::Handled();})];
}
