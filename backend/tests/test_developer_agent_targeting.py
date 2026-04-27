from app.services.developer_agent import infer_targets_from_repo


def test_infer_targets_prefers_production_files_over_tests_by_default():
    files = [
        'src/Purist/Core/MarkdownWriter.cs',
        'src/Purist/Core/ResultsFormatter.cs',
        'src/Purist.Tests/Core/MarkdownWriterTests.cs',
        'src/Purist.Tests/Core/ResultsFormatterTests.cs',
        'purist.config.sample.jsonc',
    ]

    targets = infer_targets_from_repo('Add markdown output support for results', files)

    assert 'src/Purist/Core/MarkdownWriter.cs' in targets[:3]
    assert 'src/Purist/Core/ResultsFormatter.cs' in targets[:3]


def test_infer_targets_prefers_tests_when_prompt_explicitly_mentions_tests():
    files = [
        'src/Purist/Core/MarkdownWriter.cs',
        'src/Purist.Tests/Core/MarkdownWriterTests.cs',
        'src/Purist.Tests/Core/CliArgumentParserTests.cs',
    ]

    targets = infer_targets_from_repo('Add tests for markdown output support', files)

    assert 'src/Purist.Tests/Core/MarkdownWriterTests.cs' in targets
    assert 'src/Purist.Tests/Core/CliArgumentParserTests.cs' in targets


def test_infer_targets_prefers_named_production_files_even_when_tests_are_requested():
    files = [
        'src/Purist/Program.cs',
        'src/Purist/Core/ReviewOutput.cs',
        'src/Purist.Tests/Core/CliArgumentParserTests.cs',
        'src/Purist.Tests/Core/ConfigBootstrapperTests.cs',
    ]

    targets = infer_targets_from_repo('Add Markdown results output to Purist CLI; update ReviewOutput/Program and add tests.', files)

    assert 'src/Purist/Program.cs' in targets[:3]
    assert 'src/Purist/Core/ReviewOutput.cs' in targets[:3]
