"""extract turns report text into a starter claims file. It does not open files."""

import yaml

from claimcheck.extract import extract_claims, render_claims

from conftest import REPO


def test_sample_report_paths_and_hashes():
    text = (REPO / "examples" / "report.txt").read_text(encoding="utf-8")
    claims = extract_claims(text)
    assert claims == [
        {"name": "exists_readme_md", "type": "file_exists", "path": "README.md"},
        {"name": "exists_src_app_py", "type": "file_exists", "path": "src/app.py"},
        {"name": "exists_docs_guide_md", "type": "file_exists", "path": "docs/guide.md"},
        {
            "name": "md5_src_app_py",
            "type": "file_md5",
            "path": "src/app.py",
            "md5": "0123456789abcdef0123456789abcdef",
        },
        {
            "name": "md5_readme_md",
            "type": "file_md5",
            "path": "README.md",
            "md5": "abcdef0123456789abcdef0123456789",
        },
        {"name": "exists_notes_today_txt", "type": "file_exists", "path": "notes/today.txt"},
        {
            "name": "md5_notes_today_txt",
            "type": "file_md5",
            "path": "notes/today.txt",
            "md5": "fedcba9876543210fedcba9876543210",
        },
        {"name": "exists_data_out_csv", "type": "file_exists", "path": "data/out.csv"},
        {"name": "exists_output_log", "type": "file_exists", "path": "./output.log"},
    ]
    loaded = yaml.safe_load(render_claims(claims, "report.txt"))
    assert loaded["claims"][0]["path"] == "README.md"
    assert loaded["claims"][3]["md5"] == "0123456789abcdef0123456789abcdef"


def test_documented_md5_forms_and_ignored_noise():
    text = "\n".join(
        [
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  path/file.txt",
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb *bin/file.txt",
            "MD5 (quoted/file.txt) = cccccccccccccccccccccccccccccccc",
            "md5 of prose/file.txt is dddddddddddddddddddddddddddddddd",
            "inline/file.txt md5: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "checksum of sum/file.txt is ffffffffffffffffffffffffffffffff",
            "md5 abcdefabcdefabcdefabcdefabcdefab for labeled/file.txt",
            "generated `out/report.json`.",
            "See https://example.com/docs/readme.md",
            "Contact user@example.com about version 1.2.3.",
            "# skipped README.md",
        ]
    )
    claims = extract_claims(text)
    by_key = {(item["type"], item["path"]): item for item in claims}
    assert by_key[("file_md5", "path/file.txt")]["md5"] == "a" * 32
    assert by_key[("file_md5", "bin/file.txt")]["md5"] == "b" * 32
    assert by_key[("file_md5", "quoted/file.txt")]["md5"] == "c" * 32
    assert by_key[("file_md5", "prose/file.txt")]["md5"] == "d" * 32
    assert by_key[("file_md5", "inline/file.txt")]["md5"] == "e" * 32
    assert by_key[("file_md5", "sum/file.txt")]["md5"] == "f" * 32
    assert by_key[("file_md5", "labeled/file.txt")]["md5"] == "abcdefabcdefabcdefabcdefabcdefab"
    assert ("file_exists", "out/report.json") in by_key
    assert not any("example.com" in item["path"] or item["path"].lower() == "readme.md" for item in claims)
    assert all(item["path"] != "README.md" for item in claims)
    assert not any(item["path"].endswith(".com") for item in claims)
    rendered = render_claims([], "empty.txt")
    assert yaml.safe_load(rendered) == {"claims": []}


def test_spaced_path_is_quoted():
    text = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  my file.txt\n"
    claims = extract_claims(text)
    assert claims[0]["path"] == "my file.txt"
    rendered = render_claims(claims, "report.txt")
    assert '"my file.txt"' in rendered
    assert yaml.safe_load(rendered)["claims"][1]["path"] == "my file.txt"
