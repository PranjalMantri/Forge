from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import FileDiff, Tool, ToolInvocation, ToolKind, ToolResult
from util.paths import ensure_parent_directory, resolve_path


class EditToolParams(BaseModel):
    path: str = Field(
        ...,
        description="Path to the file to edit (relative to working directory or absolute path)",
    )
    old_string: str = Field(
        "",
        description="The exact text to find and replace. Must match exactly including all whitespace and indentation. For new files, leave this empty.",
    )
    new_string: str = Field(
        ...,
        description="The text to replace old_string with. Can be empty to delete text",
    )
    replace_all: bool = Field(
        False, description="Replace all occurrences of old_string (default: false)"
    )


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Edit a file by replacing text. The old_string must match exactly "
        "(including whitespace and indentation) and must be unique in the file "
        "unless replace_all is true. Use this for precise, surgical edits. "
        "For creating new files or complete rewrites, use write_file instead."
    )
    kind = ToolKind.WRITE
    schema = EditToolParams

    def _no_math_error(
        self, old_string: str, old_content: str, path: Path
    ) -> ToolResult:
        lines = old_content.splitlines()

        partial_matches = []
        search_terms = old_string.split()[:5]

        if search_terms:
            first_term = search_terms[0]

            for i, line in enumerate(lines, 1):
                if first_term in line:
                    partial_matches.append((i, line.strip()[:80]))

                    if len(partial_matches) > 3:
                        break

        error_message = f"old_string not found in {str(path)}"

        if partial_matches:
            error_message += "\n\nPossible similar lines: "

            for line_num, line_preview in partial_matches:
                error_message += f"\n Line: {line_num}: {line_preview}"
        else:
            error_msg += (
                " Make sure the text matches exactly, including:\n"
                "- All whitespace and indentation\n"
                "- Line breaks\n"
                "- Any invisible characters\n"
                "Try re-reading the file using read_file tool and then editing."
            )

        return ToolResult.error_result(error_message)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = EditToolParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)

        if not path.exists():
            if params.old_string:
                return ToolResult.error_result(
                    f"File does not exist: {path}. To create a new file us an empty old_string"
                )

            ensure_parent_directory(path)
            path.write_text(params.new_string, encoding="utf-8")

            line_count = len(params.new_string.splitlines())

            return ToolResult.success_result(
                f"Created {path} {line_count} lines",
                diff=FileDiff(
                    path=path,
                    new_content=params.new_string,
                    old_content="",
                    is_new_file=True,
                ),
                metadata={"path": path, "is_new_file": True, "line_count": line_count},
            )

        if not params.old_string:
            return ToolResult.error_result(
                f"File exists but old_string is empty. Pass the old string to edit the file or use write_file tool to overwrite"
            )

        old_content = path.read_text(encoding="utf-8")
        occurrence_count = old_content.count(params.old_string)

        if occurrence_count == 0:
            return self._no_match_error(params.old_string, old_content, path)

        if occurrence_count > 1 and not params.replace_all:
            return ToolResult.error_result(
                f"old_string found {occurrence_count} times in {path}. "
                f"Either: \n"
                f"1. Provide more context to make the match unique or\n"
                f"2. Set replace_all=true to replace all occurrences",
                metadata={
                    "occurence_count": occurrence_count,
                },
            )

        if params.replace_all:
            new_content = old_content.replace(params.old_string, params.new_string)
            replace_count = occurrence_count
        else:
            new_content = old_content.replace(params.old_string, params.new_string, 1)
            replace_count = 1

        if new_content == old_content:
            return ToolResult.error_result(
                f"No changes were made - old_string is the same as new_string"
            )

        try:
            path.write_text(new_content, encoding="utf-8")
        except IOError as e:
            return ToolResult.error_result(f"Failed to write file: {e}")

        old_lines = len(old_content.splitlines())
        new_lines = len(new_content.splitlines())
        diff_lines = new_lines - old_lines

        diff_msg = ""

        if diff_lines > 0:
            diff_msg = f" +({diff_lines} lines)"
        else:
            diff_msg = f" ({diff_lines} lines)"

        ddiff = FileDiff(path=path, old_content=old_content, new_content=new_content)
        print("ddiff: ", ddiff)
        return ToolResult.success_result(
            f"Edited {path}: replaced {replace_count} occurrence(s){diff_msg}",
            diff=FileDiff(path=path, old_content=old_content, new_content=new_content),
            metadata={
                "path": str(path),
                "replaced_count": replace_count,
                "line_diff": diff_lines,
            },
        )
