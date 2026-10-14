# Change log

One entry per PR, newest first: ticket key, what, why.

- KAN-160: Daily report masks customer phone numbers as 415-555-****; new fieldops/audit.py logs who assigned or closed an order, and when, to an append-only data/audit.log.
  Why: Compliance does not want full phone numbers printed and wants an audit trail of assign and close actions.

