using UnrealBuildTool;

public class MajesticForge : ModuleRules
{
    public MajesticForge(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        // Native handlers have translation-unit-local helpers with shared names.
        // Keep this independent of adaptive unity's machine-local working set.
        bUseUnity = false;
        PrivateDependencyModuleNames.AddRange(new string[] {
            "Foliage", "Landscape", "Core", "CoreUObject", "Engine", "PhysicsCore", "UnrealEd", "Json", "Sockets", "Networking", "BlueprintGraph",
            "Slate", "SlateCore", "InputCore", "ToolMenus", "Projects", "KismetCompiler", "AssetRegistry", "LevelEditor", "EditorFramework",
            "GameplayAbilities", "GameplayTags", "GameplayTasks", "MajesticForgeRuntime", "WebBrowser",
            "MeshDescription", "StaticMeshDescription", "InterchangeEngine", "ContentBrowser", "MaterialEditor", "RHI", "RenderCore", "ImageWrapper", "UMG", "UMGEditor"
        });
        if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicSystemLibraries.AddRange(new string[] { "Advapi32.lib", "Bcrypt.lib" });
        }
    }
}
