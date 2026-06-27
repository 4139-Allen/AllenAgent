"""工具测试 — 参数校验、执行"""

import pytest
from tools.file_tool import FileTool
from tools.shell_tool import ShellTool


class TestFileTool:
    def test_validate_params_read(self, file_tool):
        """read 操作校验"""
        valid, err = file_tool.validate_params({"action": "read", "filepath": "test.txt"})
        assert valid
        assert err == ""

    def test_validate_params_missing_action(self, file_tool):
        """缺少 action 参数"""
        valid, err = file_tool.validate_params({"filepath": "test.txt"})
        assert not valid
        assert "缺少必填参数" in err

    def test_validate_params_invalid_action(self, file_tool):
        """无效的 action 值"""
        valid, err = file_tool.validate_params({"action": "invalid"})
        assert not valid
        assert "无效" in err
        assert "read" in err or "允许值" in err

    def test_validate_params_delete_batch(self, file_tool):
        """批量删除参数"""
        valid, err = file_tool.validate_params({
            "action": "delete",
            "filepaths": ["a.txt", "b.txt"],
        })
        assert valid

    def test_validate_params_list(self, file_tool):
        """list 操作（通过 action=list）"""
        valid, err = file_tool.validate_params({"action": "list", "filepath": "/tmp"})
        assert valid

    def test_execute_read_nonexistent(self, file_tool):
        """读取不存在的文件"""
        result = file_tool.execute(action="read", filepath="/nonexistent_file_xyz")
        assert not result.success
        assert "不存在" in (result.error or "")

    def test_validate_params_bad_type(self, file_tool):
        """参数类型错误（filepaths 应为数组）"""
        valid, err = file_tool.validate_params({
            "action": "delete",
            "filepaths": "not_a_list",
        })
        assert not valid


class TestShellTool:
    def test_validate_params(self, shell_tool):
        """shell 命令参数校验"""
        valid, err = shell_tool.validate_params({"command": "echo hello"})
        assert valid

    def test_validate_params_missing_command(self, shell_tool):
        """缺少 command 参数"""
        valid, err = shell_tool.validate_params({})
        assert not valid
        assert "缺少必填参数" in err

    def test_execute_echo(self, shell_tool):
        """执行 echo 命令"""
        result = shell_tool.execute(command="echo hello_world")
        assert result.success
        data = result.data
        assert "hello_world" in data["stdout"]
        assert data["exit_code"] == 0
