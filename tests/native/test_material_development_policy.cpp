// SPDX-License-Identifier: MIT
#include "../../Plugins/Forge/Source/MajesticForge/Private/ForgeMaterialDevelopmentPolicy.h"
#include <cstdio>

using namespace ForgeMaterialDevelopment;
int main()
{
    int Failures = 0, Cases = 0;
    auto Expect = [&](const char* Path, const char* AuthPath, const char* Consent,
        bool State, bool Create, bool Action, bool Shape, bool Expected)
    {
        ++Cases;
        if (Allowed(Path, AuthPath, Consent, State, Create, Action, Shape) != Expected) ++Failures;
    };
    Expect(Target, Target, Permission, true, false, true, true, true);
    Expect(Target, Target, nullptr, true, false, true, true, false);
    Expect(Target, Target, "yes", true, false, true, true, false);
    Expect("/Game/Other", Target, Permission, true, false, true, true, false);
    Expect(Target, "/Game/Other", Permission, true, false, true, true, false);
    Expect("/jasperprism/materials/m_jasperprism_pp", Target, Permission, true, false, true, true, false);
    Expect(Target, Target, Permission, false, false, true, true, false);
    Expect(Target, Target, Permission, true, true, true, true, false);
    Expect(Target, Target, Permission, true, false, false, true, false);
    Expect(Target, Target, Permission, true, false, true, false, false);
    Expect(nullptr, Target, Permission, true, false, true, true, false);
    Expect(Target, nullptr, Permission, true, false, true, true, false);
    auto ExpectCreation = [&](const char* Path, const char* AuthPath, const char* Consent,
        const char* State, bool DestinationAbsent, bool Creation, bool Action, bool Expected)
    {
        ++Cases;
        if (AllowedCreation(Path, AuthPath, Consent, State, DestinationAbsent, Creation, Action) != Expected) ++Failures;
    };
    ExpectCreation(CreationTarget, CreationTarget, CreationPermission, "absent", true, true, true, true);
    ExpectCreation(CreationTarget, CreationTarget, nullptr, "absent", true, true, true, false);
    ExpectCreation(CreationTarget, CreationTarget, "yes", "absent", true, true, true, false);
    ExpectCreation("/JasperPrism/materials/M_ForgeMCP_Test", CreationTarget, CreationPermission, "absent", true, true, true, false);
    ExpectCreation("/JasperPrism/Materials/M_JasperPrism_PP", CreationTarget, CreationPermission, "absent", true, true, true, false);
    ExpectCreation("/Game/Other", CreationTarget, CreationPermission, "absent", true, true, true, false);
    ExpectCreation(CreationTarget, "/Game/Other", CreationPermission, "absent", true, true, true, false);
    ExpectCreation(CreationTarget, CreationTarget, CreationPermission, "present", true, true, true, false);
    ExpectCreation(CreationTarget, CreationTarget, CreationPermission, "absent", false, true, true, false);
    ExpectCreation(CreationTarget, CreationTarget, CreationPermission, "absent", true, false, true, false);
    ExpectCreation(CreationTarget, CreationTarget, CreationPermission, "absent", true, true, false, false);
    std::printf("%d native authorization cases, %d failures\n", Cases, Failures);
    return Failures ? 1 : 0;
}
