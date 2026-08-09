from brainlib import cli


def test_no_args_is_usage_error(capsys):
    assert cli.main([]) == 2


def test_unknown_command_is_usage_error():
    assert cli.main(["nope"]) == 2
