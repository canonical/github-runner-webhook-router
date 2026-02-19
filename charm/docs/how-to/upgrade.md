# Upgrade

Before updating the charm, we recommend you to back up the database using the MongoDB charm’s `create-backup` action.

```bash
juju run mongodb-k8s/leader create-backup
```

Additional information can be found about backing up in the MongoDB charm's [documentation](https://canonical-charmed-mongodb.readthedocs-hosted.com/6/how-to/back-up-and-restore/create-a-backup/).

Then you can upgrade the `github-runner-webhook-router` charm:

```bash
juju refresh github-runner-webhook-router
```

Verify if the charm is active and idle by running the `juju status --wait 1s` command.
