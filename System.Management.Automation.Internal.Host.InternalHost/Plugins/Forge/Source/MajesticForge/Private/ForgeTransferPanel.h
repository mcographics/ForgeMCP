#pragma once
#include "CoreMinimal.h"
#include "HAL/PlatformProcess.h"
class SWidget;

// A bounded UI client of the same preview/apply MCP tools, not another bridge.
class FForgeTransferPanel
{
    FString Root=TEXT("G:/ForgeMCP"), BlenderSession, BlenderObject, Destination=TEXT("/Game/Content/Returns/"), ObjectName;
    TArray<TSharedPtr<FString>> ExportFormats;
    TSharedPtr<FString> SelectedExportFormat;
    bool bReplaceExisting=false;
    FString Status=TEXT("Select a static mesh asset or actor, then Send to Blender."), Buffer, PreviewId;
    FProcHandle Process;
    void *Read=nullptr, *ChildWrite=nullptr, *ChildRead=nullptr, *Write=nullptr;
    bool bApplying=false;
    double Started=0;
    void Close();
    void Begin(bool Send, const FString& Session, const FString& Format=TEXT("fbx"));
public:
    ~FForgeTransferPanel();
    bool Busy() const { return Process.IsValid(); }
    bool CanConfirm() const { return Busy() && !PreviewId.IsEmpty() && !bApplying; }
    bool IsApplying() const { return bApplying; }
    const FString& StatusText() const { return Status; }
    const FString& HandoffRoot() const { return Root; }
    const FString& BlenderSessionId() const { return BlenderSession; }
    const FString& BlenderObjectName() const { return BlenderObject; }
    const FString& UnrealDestination() const { return Destination; }
    const FString& UnrealObjectName() const { return ObjectName; }
    FString ExportFormat() const { return SelectedExportFormat.IsValid() ? *SelectedExportFormat : TEXT("fbx"); }
    bool ReplaceExisting() const { return bReplaceExisting; }
    void Configure(const FString& InRoot, const FString& InBlenderSession, const FString& InBlenderObject,
        const FString& InDestination, const FString& InObjectName, const FString& InFormat, bool bInReplace);
    void SendToBlender(const FString& UnrealSession);
    void SendToUnreal(const FString& UnrealSession);
    void Confirm();
    void Cancel();
    void Tick();
    TSharedRef<SWidget> Widget(TFunction<FString()> Session);
};
