# Deploying the app

A pull request into `develop` only shows a plan for the dev environment. It builds no image and changes nothing in AWS;
read the plan in the job log.

A push to `develop` (a merged pull request) builds the API image once, pushes it to the image repository and applies it to
Environment `dev`, publishes `front-end/` to the site, then runs `scripts/smoke.sh` against it. Then `production` waits for the reviewer of the
Environment `production` (you) to approve, applies the same image and checks the home page and `/api/health` only (no test sign-up in real data). Run the workflow by hand from the Actions tab
(workflow_dispatch) to deploy again without a change.

The deploy (not the pull request plan) stops with an error if it would delete or replace anything. If that is intended, add the label `allow-destroy` to the pull request before it is merged.

Repository variables (Settings, Secrets and variables, Actions, Variables), set once from the account's outputs:
AWS_ACCOUNT_ID, AWS_REGION, STATE_BUCKET, ALARM_TOPIC_ARN, PLAN_PR_ROLE_ARN, APPLY_ROLE_ARN_DEV,
APPLY_ROLE_ARN_PRODUCTION, BOUNDARY_ARN_DEV, BOUNDARY_ARN_PRODUCTION, ECR_REPOSITORY. The account administrator gives you
all of them, ECR_REPOSITORY included.

The Region is Auckland (ap-southeast-6), set by the AWS_REGION variable.

Environments (Settings, Environments): `dev` has no reviewer; `production` lists you as the required reviewer.

To change a setting, edit `infra/app/dev.tfvars.json` or `infra/app/production.tfvars.json`, open a pull request, read the
plan, merge. To change the app, change `back-end/` or `front-end/` the same way.

To roll back: re-running an earlier production run restores that version of the app; the data in S3 is not rolled back.
