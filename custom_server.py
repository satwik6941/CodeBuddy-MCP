from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

mcp = FastMCP(
    name="Custom_Tools_Server"
)

@mcp.prompt(
    name="summarise_converstation",
    description="Gives a proper summarise the conversation history into key points.",
)
def summarise_conversation(conversation_history: str) -> list[base.Message]:
    return [
        base.Message(
            role="assistant",
            content="You are an expert programmer who writes clean, efficient code."
        ),
        base.Message(
            role="user",
            content=f"Here is the code: {conversation_history}"
        )
    ]

if __name__ == "__main__":
    mcp.run(transport="stdio")