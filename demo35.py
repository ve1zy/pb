import asyncio
from release_assistant import run_release_pipeline

print("=" * 60)
print("  AI Release Assistant Demo")
print("=" * 60)
print()
print("This demo will:")
print("1. Get repository state (branch, tags)")
print("2. Fetch commits since last tag")
print("3. AI analyzes commits and generates changelog")
print("4. AI suggests next version (semver)")
print("5. Show release preview (dry run)")
print()
print("Press Enter to start...")
input()

result = asyncio.run(run_release_pipeline(dry_run=True))

print("\n" + "=" * 60)
print("  Summary")
print("=" * 60)
print(f"Version: {result['version']}")
print(f"Previous tag: {result['tag'] or 'none'}")
print(f"\nChangelog:\n{result['changelog']}")
print("\nTo create actual release, run:")
print("  python -c \"import asyncio; from release_assistant import run_release_pipeline; asyncio.run(run_release_pipeline(dry_run=False))\"")
