// SPDX-License-Identifier: MIT
#pragma once

// Engine-independent decision table, also exercised by the native regression test.
namespace ForgeMaterialValidation
{
enum class EState { Pending, Succeeded, Failed, Unavailable, TimedOut };

struct FSnapshot
{
    bool Available = false;
    bool HasResource = false;
    bool HasErrors = false;
    bool Pending = false;
    bool HasMap = false;
    bool Finalized = false;
    bool Successful = false;
    bool Complete = false;
    bool HasShaders = false;
    bool MapIdentityMatches = false;
    bool LazyShaderJobMode = false;
    bool CompletionObserved = false;
};

constexpr EState Classify(const FSnapshot& S, bool DeadlineReached = false)
{
    if (S.HasErrors) return EState::Failed;
    if (!S.Available || !S.HasResource) return EState::Unavailable;
    if (S.Pending) return DeadlineReached ? EState::TimedOut : EState::Pending;
    if (!S.HasMap || !S.MapIdentityMatches) return EState::Unavailable;
    if (S.Finalized && !S.Successful) return EState::Failed;
    if (S.Finalized && S.Successful && S.Complete && S.HasShaders) return EState::Succeeded;
    // UE's lazy per-job cache can leave whole-map flags unset. Require a positive
    // engine result notification for this exact current map, not completeness alone.
    if (!S.Finalized && S.Complete && S.HasShaders)
    {
        if (S.LazyShaderJobMode && S.CompletionObserved) return EState::Succeeded;
        return DeadlineReached ? EState::TimedOut : EState::Pending;
    }
    // No remaining jobs and no complete map is unavailable, never implicit success.
    return EState::Unavailable;
}

constexpr const char* Name(EState State)
{
    switch (State)
    {
        case EState::Pending: return "pending";
        case EState::Succeeded: return "succeeded";
        case EState::Failed: return "failed";
        case EState::TimedOut: return "timed_out";
        default: return "unavailable";
    }
}
}
