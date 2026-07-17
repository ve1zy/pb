from release_assistant_simple import run_release_pipeline

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

result = run_release_pipeline()

print("\nSummary:")
print(f"  Version: {result['version']}")
print(f"  Previous tag: {result['tag']}")
print(f"  Commits analyzed: {len(result['commits'])}")
