import os
import shutil
from pathlib import Path

def run_migration():
    root = Path(__file__).parent
    
    # 1. Define the Perfect Project Structure
    directories = [
        "apps/desktop",
        "apps/web",
        "core/document",
        "core/schema",
        "core/commands",
        "core/engine",
        "core/validation",
        "modules/editor",
        "modules/interlinear",
        "modules/ai",
        "modules/audio",
        "modules/export",
        "infrastructure/database",
        "infrastructure/logging",
        "infrastructure/config",
        "assets/templates",
        "assets/fonts",
        "tests"
    ]

    print("🏗️ Creating new architecture scaffolding...")
    for dir_path in directories:
        target = root / dir_path
        target.mkdir(parents=True, exist_ok=True)
        
        # Make them valid python packages (except assets)
        if not dir_path.startswith("assets"):
            init_file = target / "__init__.py"
            init_file.touch(exist_ok=True)

    # 2. Move new Core files to their proper homes
    print("🚚 Moving Core Engine files to constitutional directories...")
    moves = [
        ("document.py", "core/schema/document.py"),
        ("__init__.py", "core/schema/__init__.py"),
        ("document_engine.py", "core/engine/document_engine.py"),
        ("main.py", "apps/desktop/main.py")
    ]
    for src_file, dest_path in moves:
        src_path = root / src_file
        if src_path.exists():
            shutil.move(str(src_path), str(root / dest_path))

    # 3. Archive the old src/ directory and obsolete docs to prevent AI/Dev confusion
    archive_dir = root / "_archive_old_src"
    archive_dir.mkdir(exist_ok=True)
    
    obsolete_items = [
        "src",
        "blueprint_v3.0.md",
        "docs/production_hardening_plan.md"
    ]
    for item in obsolete_items:
        item_path = root / item
        if item_path.exists():
            print(f"📦 Archiving obsolete item: {item}...")
            shutil.move(str(item_path), str(archive_dir / Path(item).name))

    print("✅ Migration complete! Project is ready for Phase 1: Core Engine Development.")

if __name__ == "__main__":
    run_migration()