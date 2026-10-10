using UnrealBuildTool;

public class MajesticForge : ModuleRules
{
    public MajesticForge(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivateDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "UnrealEd", "Json", "Sockets", "Networking",
            "Slate", "SlateCore", "ToolMenus", "BlueprintGraph", "KismetCompiler", "AssetRegistry",
            "GameplayAbilities", "GameplayTags", "GameplayTasks", "MajesticForgeRuntime"
        });
        if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicSystemLibraries.AddRange(new string[] { "Advapi32.lib", "Bcrypt.lib" });
        }
    }
}
