"""
gotemplate.py - 轻量 Go template 子集渲染引擎

功能：解析并渲染 notify.yaml 中使用的 Go template 语法
仅支持项目所需的子集：变量 {{.Field}}、{{.Field.Sub}}、
条件判断 {{if eq .A "b"}}...{{else}}...{{end}}、{{if .A}}...{{end}}
"""
import re


class GoTemplate:
    """极简 Go template 渲染器（仅覆盖项目所需语法）"""

    def __init__(self, text: str):
        self.text = text or ""
        self.tokens = self._tokenize(self.text)

    @staticmethod
    def _tokenize(text: str):
        """将模板拆分为文本段与动作段（{{...}}）"""
        tokens = []
        pos = 0
        for match in re.finditer(r"\{\{(.*?)\}\}", text, re.DOTALL):
            if match.start() > pos:
                tokens.append(("text", text[pos : match.start()]))
            tokens.append(("action", match.group(1).strip()))
            pos = match.end()
        if pos < len(text):
            tokens.append(("text", text[pos:]))
        return tokens

    def render(self, context: dict) -> str:
        """渲染模板，返回字符串"""
        return self._render_tokens(self.tokens, context)

    @staticmethod
    def _resolve(path: str, context: dict):
        """按 .Field.Sub 路径从上下文中取值"""
        path = path.strip()
        if not path.startswith("."):
            # 字面量（如 "high"）
            if path.startswith('"') and path.endswith('"'):
                return path[1:-1]
            return path
        # 去掉开头的点，按点切分
        parts = [p for p in path[1:].split(".") if p]
        value = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return ""
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _eval_cond(expr: str, context: dict) -> bool:
        """求值条件表达式，支持 eq / ne / 单变量真值"""
        tokens = expr.split()
        if not tokens:
            return False
        if tokens[0] in ("eq", "ne"):
            left = GoTemplate._resolve(tokens[1], context)
            right = GoTemplate._resolve(" ".join(tokens[2:]), context)
            if tokens[0] == "eq":
                return left == right
            return left != right
        # 单变量真值判断
        val = GoTemplate._resolve(expr, context)
        return bool(val) and val.lower() not in ("false", "0", "none", "")

    def _render_tokens(self, tokens: list, context: dict) -> str:
        out = []
        i = 0
        n = len(tokens)
        while i < n:
            kind, val = tokens[i]
            if kind == "text":
                out.append(val)
                i += 1
                continue
            if val.startswith("if "):
                cond = self._eval_cond(val[3:].strip(), context)
                # 条件为真取 true 分支，为假取 {{else}} 分支（无 else 时为空串）
                i, true_body, false_body = self._collect_block(tokens, i + 1, context)
                out.append(true_body if cond else false_body)
                continue
            if val in ("else", "end"):
                # 顶层出现 else/end 视为无效，跳过
                i += 1
                continue
            # 变量或字面量
            out.append(self._resolve(val, context))
            i += 1
        return "".join(out)

    def _collect_block(self, tokens: list, start: int, context: dict):
        """
        收集 if 块内容，处理嵌套与 else 分支。
        返回 (next_index, rendered_true, rendered_false)

        - rendered_true ：{{if}} 与 {{else}}（或 {{end}}）之间的内容；
        - rendered_false：{{else}} 与 {{end}} 之间的内容，无 else 时为空串。
        由调用方按条件真假二选一。（旧实现只渲染 true 分支并直接丢弃 false_buf，
        导致 docstring 中声明支持的 {{else}} 永远不会被输出。）
        """
        depth = 1
        true_buf = []
        false_buf = []
        current = true_buf
        i = start
        n = len(tokens)
        while i < n:
            kind, val = tokens[i]
            if kind == "text":
                current.append((kind, val))
                i += 1
                continue
            if val.startswith("if "):
                depth += 1
                current.append((kind, val))
                i += 1
                continue
            if val == "end":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
                current.append((kind, val))
                i += 1
                continue
            if val == "else":
                # 仅本层的 else 才切换缓冲区；嵌套 if 内的 else 原样保留，
                # 由递归渲染该子块时再处理
                if depth == 1:
                    current = false_buf
                else:
                    current.append((kind, val))
                i += 1
                continue
            current.append((kind, val))
            i += 1
        # 两个分支都渲染出来交给调用方选择（分支内仅做取值/拼接，无副作用）
        return i, self._render_tokens(true_buf, context), self._render_tokens(false_buf, context)
