// SPDX-License-Identifier: MIT
#include "../../Plugins/Forge/Source/MajesticForge/Private/ForgeMaterialValidationState.h"
#include <cstdio>

using namespace ForgeMaterialValidation;
int main()
{
    int Cases = 0;
    int Failures = 0;
    auto Expect = [&](const char* Label, FSnapshot Snapshot, EState Expected, bool Deadline = false)
    {
        ++Cases;
        const EState Actual = Classify(Snapshot, Deadline);
        if (Actual != Expected)
        {
            ++Failures;
            std::printf("FAIL %s: expected %s, got %s\n", Label, Name(Expected), Name(Actual));
        }
    };
    const FSnapshot Ready{true, true, false, false, true, true, true, true, true, true};
    Expect("complete successful map", Ready, EState::Succeeded);
    Expect("complete at deadline", Ready, EState::Succeeded, true);
    Expect("empty default is unavailable", {}, EState::Unavailable);
    auto S = Ready; S.Available = false;
    Expect("compiler skipped or unavailable", S, EState::Unavailable);
    S = Ready; S.HasResource = false;
    Expect("missing resource", S, EState::Unavailable);
    S = Ready; S.HasMap = false;
    Expect("missing map with empty errors", S, EState::Unavailable);
    S.Pending = true;
    Expect("pending cache before map", S, EState::Pending);
    Expect("pending cache timeout", S, EState::TimedOut, true);
    S = Ready; S.Pending = true;
    Expect("pending jobs with previous successful map", S, EState::Pending);
    Expect("pending jobs timeout", S, EState::TimedOut, true);
    S.HasErrors = true;
    Expect("compiler error during pending work", S, EState::Failed);
    Expect("error wins over timeout", S, EState::Failed, true);
    S = Ready; S.HasErrors = true;
    Expect("error wins over complete map", S, EState::Failed);
    S = Ready; S.Successful = false;
    Expect("finalized failure without compiler text", S, EState::Failed);
    S = Ready; S.Finalized = false;
    Expect("complete map awaiting finalization", S, EState::Pending);
    Expect("finalization timeout", S, EState::TimedOut, true);
    S.Pending = true;
    Expect("unfinalized with pending work", S, EState::Pending);
    S = Ready; S.Complete = false;
    Expect("incomplete successful map", S, EState::Unavailable);
    S.Pending = true;
    Expect("incomplete map while compiling", S, EState::Pending);
    S = Ready; S.HasShaders = false;
    Expect("empty successful map", S, EState::Unavailable);
    S = {}; S.HasErrors = true;
    Expect("translation errors without resource or map", S, EState::Failed);
    S = Ready; S.MapIdentityMatches = false;
    Expect("stale material/platform/quality map", S, EState::Unavailable);
    S = Ready; S.Finalized = false; S.Successful = false;
    Expect("observed nine-shader state without completion proof", S, EState::Pending);
    S.LazyShaderJobMode = true;
    Expect("lazy completeness alone is insufficient", S, EState::Pending);
    Expect("missing lazy completion proof times out", S, EState::TimedOut, true);
    S.CompletionObserved = true;
    Expect("positive engine result in lazy shader-job mode", S, EState::Succeeded);
    Expect("positive lazy result at deadline", S, EState::Succeeded, true);
    S.Pending = true;
    Expect("positive notification cannot bypass outstanding work", S, EState::Pending);
    Expect("outstanding work still times out", S, EState::TimedOut, true);
    S.Pending = false; S.HasErrors = true;
    Expect("lazy proof cannot bypass compiler errors", S, EState::Failed);
    S.HasErrors = false; S.Finalized = true;
    Expect("explicit finalized failure cannot use lazy proof", S, EState::Failed);
    S.Finalized = false; S.MapIdentityMatches = false;
    Expect("lazy proof for stale map rejected", S, EState::Unavailable);
    S.MapIdentityMatches = true; S.HasShaders = false;
    Expect("lazy proof with zero shaders rejected", S, EState::Unavailable);
    S.HasShaders = true; S.Complete = false;
    Expect("lazy proof with incomplete map rejected", S, EState::Unavailable);
    S.Complete = true; S.LazyShaderJobMode = false;
    Expect("legacy mode still requires final flags", S, EState::Pending);
    Expect("legacy finalization remains bounded", S, EState::TimedOut, true);
    std::printf("%d native shader-validation cases, %d failures\n", Cases, Failures);
    return Failures ? 1 : 0;
}
