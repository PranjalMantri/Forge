from tools.subagent import SubAgentDefinition

TEST_SUBAGENT = SubAgentDefinition(
    name="test",
    description="A simple testing subagent",
    goal_prompt="""
You are a testing subagent.

Your job is to answer the user's request as accurately as possible.
Use read_file and grep if needed.
Do not modify files.
""",
    allowed_tools=[
        "read_file",
        "grep",
        "list_dir",
    ],
    max_turns=5,
    timeout_seconds=120,
)