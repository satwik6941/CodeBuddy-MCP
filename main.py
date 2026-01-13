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
    
    # Setup E2B (instead of shell MCP)
    mcp_connections.setup_e2b(os.getenv("E2B_API_KEY"))
    
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
        await setup_assistant()
        
        claude_client = llm.init_claude(os.getenv("CLAUDE_API_KEY"))
        
        # Interactive mode
        print("\n" + "="*60)
        print("INTERACTIVE MODE - Type 'exit' to quit")
        print("="*60)
        
        while True:
            user_input = input("\n👤 You: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            
            if not user_input:
                continue
            
            response = await llm.send_message(claude_client, user_input)
            print(f"\n🤖 Claude: {response}")
        
    finally:
        await mcp_connections.close_all_servers()
        print("\n Assistant shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())