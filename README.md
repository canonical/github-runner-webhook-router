<!-- vale Canonical.007-Headings-sentence-case = NO -->
# GitHub runner webhook router
<!-- vale Canonical.007-Headings-sentence-case = YES -->

[![CharmHub Badge](https://charmhub.io/github-runner-webhook-router/badge.svg)](https://charmhub.io/github-runner-webhook-router)
[![Promote charm](https://github.com/canonical/github-runner-webhook-router/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/github-runner-webhook-router/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

This charm provides a webhook router for self-hosted GitHub Actions runners. 
It is designed to be used in conjunction with the [GitHub Runner](https://github.com/canonical/github-runner-operator) charm.

The charm was built using the [paas-charm](https://github.com/canonical/paas-charm)  approach and runs on Kubernetes.

The router is a Flask application that listens for incoming webhooks from GitHub and routes them 
to the appropriate GitHub Runner charm application, which then spawns a runner to execute the job.
It is a critical component for the "reactive" mode of the GitHub Runner Charm.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more.
For the GitHub Runner Webhook Router, this includes

* All the general and Flask-related features of [paas-charm](https://github.com/canonical/paas-charm)
* Configuring the routing table
* Configuring a webhook secret to improve the security of the webhook endpoint

For information on how to deploy, integrate and manage this charm, please see the official
[GitHub Runner Webhook Router Documentation](https://charmhub.io/github-runner-webhook-router).

## Get started
As the charm is designed to be used in conjunction with the [GitHub Runner](https://github.com/canonical/github-runner-operator) charm,
please see [How to set up reactive spawning](https://charmhub.io/github-runner/docs/how-to-reactive) to learn how to deploy the charm.


### Basic operations

Configure a routing table to decide which labels should be routed to which GitHub Runner charm application:

```shell
cat <<EOF > routing_table.yaml
- large: [large, x64]
- large-arm: [large, arm64]
- small: [small]
EOF
juju config github-runner-webhook-router routing-table="$(cat routing_table.yaml)"
```

Change the default flavor to be used for jobs only containing default self-hosted-labels:

```shell
juju config github-runner-webhook-router default-flavour=small
```

Change the webhook secret used for webhook validation:

```shell
juju config github-runner-webhook-router webhook-secret=<your-secret>
```

In an error scenario, you may want to redeliver failed webhook deliveries. You can use
the `redeliver-failed-webhooks` action to redeliver failed webhook deliveries. The following 
example redelivers failed deliveries since last minute for a webhook with ID `516986490`

```shell
juju add-secret github-token token=<your-token> # the token needs webhook write permissions
# output is: secret:ctik2gfmp25c7648t7j0
juju run-action github-runner-webhook-router/0 redeliver-failed-webhook github-path=canonical/github-runner-webhook-router webhook-id=516986490 since=60 github-token-secret-id=ctik2gfmp25c7648t7j0
```

### Integrations

The charm requires an integration with MongoDB (either the [machine](https://charmhub.io/mongodb)
or [k8s](https://charmhub.io/mongodb-k8s) charm), otherwise it will go into a blocked state.
For a complete list of integrations, 
see the [Charmhub documentation](https://charmhub.io/github-runner-webhook-router/integrations).


## Learn more
* [Read more](https://charmhub.io/github-runner-webhook-router)
* [Developer documentation](https://github.com/canonical/github-runner-webhook-router/blob/main/CONTRIBUTING.md)
* [PaaS Charm repository](https://github.com/canonical/paas-charm)
* [Write your first Kubernetes charm for a Flask app](https://documentation.ubuntu.com/charmcraft/stable/tutorial/kubernetes-charm-flask/)
* [How to build a 12-Factor app charm](https://documentation.ubuntu.com/charmcraft/stable/howto/manage-web-app-charms/)
* [Troubleshooting](https://matrix.to/#/#12-factor-charms:ubuntu.com)

## Project and community
* [Issues](https://github.com/canonical/github-runner-operator/issues)
* [Contributing](https://charmhub.io/github-runner/docs/how-to-contribute)
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
