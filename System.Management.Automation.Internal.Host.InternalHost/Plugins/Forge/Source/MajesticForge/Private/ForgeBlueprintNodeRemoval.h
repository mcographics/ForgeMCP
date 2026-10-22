#pragma once
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "UObject/StrongObjectPtr.h"

namespace ForgeBlueprintNodeRemoval
{
inline bool Allowed(UEdGraphNode* Node)
{
    if (!Node || !Node->CanUserDeleteNode()) return false;
    const FString Class = Node->GetClass()->GetPathName();
    static const TSet<FString> Classes{
        TEXT("/Script/BlueprintGraph.K2Node_CallFunction"),
        TEXT("/Script/BlueprintGraph.K2Node_PromotableOperator"),
        TEXT("/Script/BlueprintGraph.K2Node_CommutativeAssociativeBinaryOperator"),
        TEXT("/Script/BlueprintGraph.K2Node_IfThenElse"),
        TEXT("/Script/BlueprintGraph.K2Node_MacroInstance"),
        TEXT("/Script/BlueprintGraph.K2Node_VariableGet"),
        TEXT("/Script/BlueprintGraph.K2Node_VariableSet"),
        TEXT("/Script/BlueprintGraph.K2Node_Knot")};
    return Classes.Contains(Class);
}

// Keep original objects alive until compilation succeeds. Reinsert them before
// the existing snapshot restores their exact pins, defaults and connections.
struct FRemovedNode
{
    TStrongObjectPtr<UEdGraphNode> Node;
    TStrongObjectPtr<UEdGraph> Graph;
    explicit FRemovedNode(UEdGraphNode* Value) : Node(Value), Graph(Value->GetGraph()) {}
    void Restore() const
    {
        if (!Graph->Nodes.Contains(Node.Get())) Graph->AddNode(Node.Get(), false, false);
    }
};
}
