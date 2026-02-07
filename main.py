# main.py
import asyncio
import os
import mcp_connections
import llm


async def setup_assistant():
    """Setup the AI assistant"""
    print("🚀 Setting up CodeBuddy MCP....\n")
    
    # Connect to GitHub MCP
    await mcp_connections.connect_github_server(os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"))

    # Setup Docker for code execution (instead of E2B)
    mcp_connections.setup_docker("./workspace")
    
    # Show available tools
    print("\n📋 Available Tools:")
    summary = mcp_connections.get_tools_summary()
    for server, tools in summary.items():
        print(f"\n{server.upper()}:")
        for tool in tools:
            print(f"  • {tool}")
    print("\n" + "="*60)


async def main():
    """Main entry point"""
    try:
        # First, get user's problem statement
        print("\n" + "="*60)
        print("CODEBUDDY MCP - AI Development Assistant")
        print("="*60)
        print("\nPlease describe your problem statement or what you'd like to work on:")
        problem_statement = input("👤 Problem: ").strip()

        if not problem_statement:
            print("No problem statement provided. Exiting...")
            return

        # Show API choices
        print("\n" + "="*60)
        print("SELECT API PROVIDER")
        print("="*60)
        print("\n1. Anthropic API (Official Claude API)")
        print("2. Open Router API (Access to multiple models)")
        print("\nWhich API would you like to use?")

        api_choice = input("Enter choice (1 or 2): ").strip()

        # Initialize client based on choice
        client = None
        model = None

        if api_choice == "1":
            # Use Anthropic API
            api_key = os.getenv("CLAUDE_API_KEY")
            if not api_key:
                print("\n❌ Error: CLAUDE_API_KEY not found in environment variables")
                return
            client = llm.init_claude(api_key)
            print("\n✓ Using Anthropic API")
        elif api_choice == "2":
            # Use Open Router API
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                print("\n❌ Error: OPENROUTER_API_KEY not found in environment variables")
                print("Please add OPENROUTER_API_KEY to your .env file")
                return

            # Ask for model selection
            print("\n" + "="*60)
            print("SELECT MODEL (Open Router)")
            print("="*60)
            print("\nPopular models:")
            print("1. anthropic/claude-sonnet-4.5 (Recommended)")
            print("2. anthropic/claude-opus-4-20250514")
            print("3. openai/gpt-4o")
            print("4. google/gemini-2.0-flash-exp:free")
            print("5. Enter custom model name")

            model_choice = input("\nEnter choice (1-5): ").strip()

            if model_choice == "1":
                model = "anthropic/claude-sonnet-4.5"
            elif model_choice == "2":
                model = "anthropic/claude-opus-4-20250514"
            elif model_choice == "3":
                model = "openai/gpt-4o"
            elif model_choice == "4":
                model = "google/gemini-2.0-flash-exp:free"
            elif model_choice == "5":
                model = input("Enter custom model name: ").strip()
            else:
                print("Invalid choice, using default: anthropic/claude-sonnet-4.5")
                model = "anthropic/claude-sonnet-4.5"

            client = llm.init_openrouter(api_key)
            print(f"\n✓ Using Open Router API with model: {model}")
        else:
            print("\n❌ Invalid choice. Please select 1 or 2.")
            return

        # Setup assistant
        await setup_assistant()

        # Interactive mode
        print("\n" + "="*60)
        print("INTERACTIVE MODE - Type 'exit' to quit")
        print("="*60)

        # First, send the problem statement
        print(f"\nProcessing your problem statement: {problem_statement}\n")
        response = await llm.send_message(client, problem_statement, model=model)
        print(f"\n🤖 AI: {response}")

        # Continue with interactive mode
        while True:
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                break

            if not user_input:
                continue

            response = await llm.send_message(client, user_input, model=model)
            print(f"\n🤖 AI: {response}")

    finally:
        await mcp_connections.close_all_servers()
        print("\n Assistant shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())