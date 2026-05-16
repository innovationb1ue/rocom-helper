import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

try:
    from src.main import main_menu
    main_menu()
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

try:
    input("\nPress Enter to exit...")
except:
    pass
