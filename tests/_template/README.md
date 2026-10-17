# External gate-test template

Do not edit this directory into a live registry test in place.

Copy the two template files into a new versioned test directory:

```bash
TEST_ID=MGTEST-NARF-YOURCASE-001
mkdir -p "tests/${TEST_ID}/v1"
cp tests/_template/manifest.template.json "tests/${TEST_ID}/v1/manifest.json"
cp tests/_template/test.template.py "tests/${TEST_ID}/v1/test.py"
```

Then:

1. replace the placeholder test ID everywhere;
2. set your GitHub username as `review.author`;
3. freeze the exact target commit and expected safe condition;
4. implement the adversarial test and a valid control path;
5. keep the status `PROPOSED` and proposal evidence `UNVERIFIED`/null;
6. run `python3 tools/validate_registry.py` and compile your `test.py`;
7. open a pull request against `miguelkolli/mgnarftest:main`.

The template skeleton deliberately exits non-zero. A contributor must implement real assertions before the test can pass.

See `/EXTERNAL-TEST-QUICKSTART.md` for the complete first-contribution flow.
