# Security

GradeOS runs on loopback only. Keep it local; this release does not provide remote-user
authentication or tenant isolation. All write endpoints check the workspace token and origin.

General tasks can read workspace text and grading outputs and save local files. They do not
have shell, arbitrary-path or browser tools. Imported Skills cannot grant additional tools.
HTML previews run with a restrictive CSP and an opaque-origin iframe sandbox.

Model requests send selected conversation and file content to the configured provider.
Provider credentials stay on the server and must never be included in bug reports.

Do not post private student material, keys or model transcripts in public issues.
Use GitHub private vulnerability reporting when enabled, or contact the maintainer privately
before sharing sensitive reproduction details. Public reports should use synthetic examples.
