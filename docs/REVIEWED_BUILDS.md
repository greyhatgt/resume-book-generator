# Reviewed local releases

`scripts/reviewed_build.py` wraps the existing generator for the build portion of
issue #4. It does not extract or change candidate metadata, sync submissions,
deploy a service, or send notifications.

Keep inputs, review receipts, intermediate files, and releases in private storage.
Use `output/` for local receipts/releases so Git ignores them. These files include
candidate filenames and resume content; never upload them as public CI artifacts
or attach build logs to public issues. The script inherits filesystem permissions;
use a private directory/ACL and `umask 077` on the Linux build host.

After a human completes the metadata review described in `AGENTS.md`, that human
records their attestation (replace `REVIEWER` and the release name):

```bash
python scripts/reviewed_build.py review --csv candidates.csv --input input \
  --receipt output/reviews/2026-09-29.json --reviewer REVIEWER --confirm-reviewed
```

The receipt binds the entire CSV and each referenced PDF to SHA-256 hashes. It is
an explicit review attestation, not authentication or proof that review happened.
Restrict receipt-writing permissions to reviewers; a future deployment job should
only consume approved receipts. Changing any input requires fresh human review
and a new receipt. Missing, duplicate, out-of-folder, or placeholder rows are
rejected instead of being silently excluded.

Build using the repository's recommended Nix environment:

```bash
nix-shell -p typst ghostscript libreoffice python313Packages.pandas python313Packages.pymupdf python313Packages.pypdf --run \
  "python scripts/reviewed_build.py build --csv candidates.csv --input input --receipt output/reviews/2026-09-29.json --release output/releases/2026-09-29"
```

The command copies reviewed inputs into a temporary snapshot, verifies hashes
again, runs the existing generator, and checks page counts, candidate outline
targets, and TOC link coverage. It then atomically renames a validated release
directory into place. It refuses an existing release name and leaves previous
releases intact. The release includes the PDF, private generation intermediates,
private build log, and a hash/validation manifest. On failure, temporary files
are removed and the command exits nonzero. This is structural validation; a human
must still inspect page appearance before deploying. Builds use the current
generator/dependencies and are not claimed to be byte-for-byte reproducible.

An exclusive `.<release-name>.build-lock` directory serializes builders using this
wrapper. After a crash, an operator may remove a stale lock only after confirming
no build is running. Keep the release parent writable only by trusted operators;
other tools must honor this lock and must not create/rename release directories
during a build. The final rename is atomic, but POSIX rename is not a general
no-replace operation against unrelated writers (an empty directory created by
another tool at the last instant could otherwise be replaced).

Offline regression tests (synthetic PDFs only):

```bash
python -m unittest discover -s tests -v
```

When `typst` is on `PATH`, the suite also runs the actual generator with two
synthetic candidates and different resume lengths. Otherwise that one integration
test is skipped. Typst may fetch its Font Awesome package on the first run; no
candidate data is sent as part of that package download.

## Remaining deployment integration

Before completing issue #4, the operator must provide the existing Headstrong
connection/service path, private reviewed input location, deployment identity,
and failure notification destination. Inspect the existing service contract before
writing deployment logic. A deployment should keep the current served PDF as a
rollback copy, copy/verify the new artifact into the same filesystem, atomically
switch it into service, verify the actual private download endpoint, and restore
the previous PDF if that check fails. Notification messages must exclude private
candidate fields, filenames, and build logs. No live deployment, rollback test,
or notification configuration is included in this change.
