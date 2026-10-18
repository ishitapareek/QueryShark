import re
from typing import List, Dict, Any
from app.models.query_model import QueryRankingOption

class SQLParserService:
    """
    Service responsible for parsing multi-statement SQL scripts (.sql files),
    stripping comments, handling string literals, and ranking executed statements.
    """

    @staticmethod
    def split_sql_statements(sql_content: str) -> List[str]:
        """
        Parses raw SQL content from a .sql file or text script and extracts
        individual executable SQL statements.
        
        Properly ignores:
        - Single-line comments (-- and #)
        - Multi-line comments (/* ... */)
        - Semicolons inside single quotes, double quotes, or backticks.
        """
        if not sql_content or not sql_content.strip():
            return []

        statements = []
        current_stmt = []
        
        in_single_quote = False
        in_double_quote = False
        in_backtick = False
        in_line_comment = False
        in_block_comment = False
        
        i = 0
        n = len(sql_content)
        
        while i < n:
            char = sql_content[i]
            next_char = sql_content[i + 1] if i + 1 < n else ""
            
            # Check comment status if not inside quotes
            if not in_single_quote and not in_double_quote and not in_backtick:
                # Line comment start: -- or #
                if not in_line_comment and not in_block_comment:
                    if (char == "-" and next_char == "-") or char == "#":
                        in_line_comment = True
                        i += 1
                        continue
                    # Block comment start: /*
                    elif char == "/" and next_char == "*":
                        in_block_comment = True
                        i += 2
                        continue

                # Line comment end: newline
                if in_line_comment:
                    if char == "\n" or char == "\r":
                        in_line_comment = False
                    i += 1
                    continue

                # Block comment end: */
                if in_block_comment:
                    if char == "*" and next_char == "/":
                        in_block_comment = False
                        i += 2
                        continue
                    i += 1
                    continue

            # Handle quotes
            if not in_line_comment and not in_block_comment:
                if char == "'" and not in_double_quote and not in_backtick:
                    # Check for escaped quote \'
                    is_escaped = (i > 0 and sql_content[i - 1] == "\\")
                    if not is_escaped:
                        in_single_quote = not in_single_quote
                elif char == '"' and not in_single_quote and not in_backtick:
                    is_escaped = (i > 0 and sql_content[i - 1] == "\\")
                    if not is_escaped:
                        in_double_quote = not in_double_quote
                elif char == '`' and not in_single_quote and not in_double_quote:
                    in_backtick = not in_backtick

                # Statement delimiter ;
                if char == ";" and not in_single_quote and not in_double_quote and not in_backtick:
                    stmt = "".join(current_stmt).strip()
                    if stmt:
                        statements.append(stmt)
                    current_stmt = []
                    i += 1
                    continue

                current_stmt.append(char)

            i += 1

        # Residual statement without trailing semicolon
        remaining = "".join(current_stmt).strip()
        if remaining:
            statements.append(remaining)

        return statements

    @staticmethod
    def rank_statements(statements: List[Dict[str, Any]], rank_by: str) -> List[Dict[str, Any]]:
        """
        Ranks a list of executed statement records based on the specified ranking criterion.
        Assigns an explicit 1-indexed 'rank' attribute.
        """
        criterion = str(rank_by).lower()

        if criterion == QueryRankingOption.DURATION_DESC.value or criterion == "duration_desc":
            sorted_stmts = sorted(statements, key=lambda x: x.get("duration_ms", 0.0), reverse=True)
        elif criterion == QueryRankingOption.DURATION_ASC.value or criterion == "duration_asc":
            sorted_stmts = sorted(statements, key=lambda x: x.get("duration_ms", 0.0), reverse=False)
        elif criterion == QueryRankingOption.STATUS.value or criterion == "status":
            # Priority: SLOW, ERROR, FAST
            status_priority = {"SLOW": 0, "ERROR": 1, "FAST": 2}
            sorted_stmts = sorted(
                statements,
                key=lambda x: (status_priority.get(x.get("status", "FAST"), 3), -x.get("duration_ms", 0.0))
            )
        elif criterion == QueryRankingOption.ROWS_AFFECTED_DESC.value or criterion == "rows_affected_desc":
            sorted_stmts = sorted(statements, key=lambda x: x.get("rows_affected", 0), reverse=True)
        elif criterion == QueryRankingOption.TIMESTAMP_DESC.value or criterion == "timestamp_desc":
            sorted_stmts = sorted(statements, key=lambda x: x.get("timestamp"), reverse=True)
        elif criterion == QueryRankingOption.TIMESTAMP_ASC.value or criterion == "timestamp_asc":
            sorted_stmts = sorted(statements, key=lambda x: x.get("timestamp"), reverse=False)
        else: # EXECUTION_ORDER default
            sorted_stmts = sorted(statements, key=lambda x: x.get("statement_index", 0), reverse=False)

        # Assign rank 1..N
        for idx, stmt in enumerate(sorted_stmts, start=1):
            stmt["rank"] = idx

        return sorted_stmts
