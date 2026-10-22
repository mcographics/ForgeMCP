// SPDX-License-Identifier: MIT
#pragma once

namespace ForgeMaterialDevelopment
{
constexpr const char* Target = "/JasperPrism/Materials/M_JasperPrism_PP";
constexpr const char* Permission = "I authorize completing the existing JasperPrism contrast graph";
constexpr const char* CreationTarget = "/JasperPrism/Materials/M_ForgeMCP_Test";
constexpr const char* CreationPermission = "I authorize creating the ForgeMCP test material at the exact target path";
constexpr bool Equal(const char* A, const char* B)
{
    if (!A || !B) return false;
    while (*A && *B) if (*A++ != *B++) return false;
    return *A == *B;
}
constexpr bool Allowed(const char* Path, const char* AuthorizationPath, const char* Consent,
    bool StateMatches, bool Creation, bool SupportedAction, bool ShapeMatches)
{
    return Equal(Path, Target) && Equal(AuthorizationPath, Target) && Equal(Consent, Permission)
        && StateMatches && !Creation && SupportedAction && ShapeMatches;
}
constexpr bool AllowedCreation(const char* Path, const char* AuthorizationPath, const char* Consent,
    const char* ExpectedState, bool DestinationAbsent, bool Creation, bool GraphAction)
{
    return Equal(Path, CreationTarget) && Equal(AuthorizationPath, CreationTarget)
        && Equal(Consent, CreationPermission) && Equal(ExpectedState, "absent")
        && DestinationAbsent && Creation && GraphAction;
}
}
