using UnrealBuildTool;

public class MajesticForgeRuntime : ModuleRules
{
    public MajesticForgeRuntime(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "GameplayAbilities", "GameplayTags", "GameplayTasks"
        });
    }
}
