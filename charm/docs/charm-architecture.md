# Charm architecture

The GitHub Runner Webhook Router is a Flask application that provides a webhook router for self-hosted GitHub Actions runners. The [GitHub Runner Webhook Router charm](https://github.com/canonical/github-runner-webhook-router/) was developed using the [12-factor Flask framework](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/extensions/flask-framework-extension/). This framework allows us to easily deploy and operate the GitHub Runner Webhook Router and its associated infrastructure, such as MongoDB and ingress.

It leverages the [12-factor](https://canonical-12-factor-app-support.readthedocs-hosted.com/en/latest/) support to pack a [Flask](https://flask.palletsprojects.com/) application providing the functionality for the webhook router.

For a complete view on the architecture of a 12-factor charm, refer to the [12-factor architecture documentation](https://canonical-12-factor-app-support.readthedocs-hosted.com/en/latest/explanation/charm-architecture/).

## Charm architecture diagram

Below is a diagram of the application architecture of the GitHub Runner Webhook Router charm.

```mermaid
C4Container

System_Boundary(webhookroutercharm, "GitHub Runner Webhook Router Charm") {

    Container_Boundary(webhookrouter_container, "GitHub Runner Webhook Router Workload Container") {
        Component(webhookrouter_core, "Webhook Router", "Flask Application", "Serves web requests, publishes messages")
    }

    Container_Boundary(charm_container, "Charm Container") {
        Component(charm_logic, "Charm Logic", "Juju Operator Framework", "Controls application deployment & config")
    }
}

Rel(charm_logic, webhookrouter_core, "Supervises<br>process")

UpdateRelStyle(charm_logic, webhookrouter_core, $offsetX="-30")

```


The charm design leverages the [sidecar](https://kubernetes.io/blog/2015/06/the-distributed-system-toolkit-patterns/#example-1-sidecar-containers) pattern to allow multiple containers in each pod with [Pebble](https://ops.readthedocs.io/en/latest/reference/pebble.html) running as the workload container’s entrypoint.

Pebble is a lightweight, API-driven process supervisor that is responsible for configuring processes to run in a container and controlling those processes throughout the workload lifecycle.

Pebble `services` are configured through [layers](https://github.com/canonical/pebble#layer-specification), and the following container represents one layer forming the effective Pebble configuration, or `plan`:

1. The GitHub Router container itself, which has a web server configured in HTTP mode.

As a result, if you run a `kubectl get pods` on a namespace named for the Juju model you've deployed the Webhook Router charm into, you'll see something like the following:

```bash
NAME                                READY   STATUS    RESTARTS        AGE
github-runner-webhook-router-0      2/2     Running   0               3d14h
```

This shows there are two containers - the one named above, as well as a container for the charm code itself.

And if you run `kubectl describe pod github-runner-webhook-router-0`, all the containers will have a command ```/charm/bin/pebble```. That's because Pebble is responsible for the processes' startup as explained above. 

## OCI images

We use [Rockcraft](https://canonical-rockcraft.readthedocs-hosted.com/en/latest/) to build the OCI image for the GitHub Runner Webhook Router charm.
The image is defined in [`github-runner-webhook-router` rock](https://github.com/canonical/github-runner-webhook-router/blob/main/rockcraft.yaml).
The rock and the charm are published to [Charmhub](https://charmhub.io/), the official repository of charms.

> See more: [How to publish your charm on Charmhub](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/howto/manage-charms/#publish-a-charm-on-charmhub)

## Metrics

Metrics are provider by the workload container at the `/metrics` endpoint at port 9102. See the [Flask framework reference](https://documentation.ubuntu.com/rockcraft/en/latest/reference/extensions/flask-framework/) for
more information about metrics in Flask applications based on [12-factor app support in Charmcraft and Rockcraft](https://canonical-12-factor-app-support.readthedocs-hosted.com).

## Juju events

For this charm, the following Juju events are observed:

1. [`app_pebble_ready`](https://documentation.ubuntu.com/juju/3.6/reference/hook/index.html#container-pebble-ready): fired on Kubernetes charms when the requested container is ready. **Action**: validate the charm configuration, run pending migrations and restart the workload.

2. [`config_changed`](https://documentation.ubuntu.com/juju/latest/reference/hook/index.html#config-changed): usually fired in response to a configuration change using the CLI. **Action**: validate the charm configuration, run pending migrations and restart the workload.

3. [`secret_storage_relation_created`](https://documentation.ubuntu.com/juju/latest/reference/hook/index.html#endpoint-relation-created): fired when the relation is first created. **Action**: generate a new secret and store it in the relation data.

4. [`secret_storage_relation_changed`](https://documentation.ubuntu.com/juju/latest/reference/hook/index.html#endpoint-relation-changed): fired when a new unit joins in an existing relation and whenever the related unit changes its settings. **Action**: validate the charm configuration, run pending migrations and restart the workload.

5. [`secret_storage_relation_departed`](https://documentation.ubuntu.com/juju/latest/reference/hook/index.html#endpoint-relation-departed): fired when a unit departs from an existing relation. **Action**: validate the charm configuration, run pending migrations and restart the workload.

6. [`update_status`](https://documentation.ubuntu.com/juju/latest/reference/hook/index.html#update-status): fired at regular intervals. **Action**: validate the configuration, run pending migrations and restart the workload.

7. [`secret_changed`](https://documentation.ubuntu.com/juju/latest/reference/hook/index.html#secret-changed): fired when the secret owner publishes a new secret revision. **Action**: validate the configuration, run pending migrations and restart the workload.

8. [`database_created`](https://github.com/canonical/data-platform-libs): fired when a new database is created. **Action**: validate the charm configuration, run pending migrations and restart the workload.

9. [`endpoints_changed`](https://github.com/canonical/data-platform-libs): fired when the database endpoints change. **Action**: validate the charm configuration, run pending migrations and restart the workload.

10. [`database_relation_broken`](https://github.com/canonical/data-platform-libs): fired when a unit participating in a non-peer relation is removed. **Action**: validate the charm configuration, run pending migrations and restart the workload.

11. [`ingress_ready`](https://github.com/canonical/traefik-k8s-operator): fired when the ingress for the app is ready. **Action**: validate the charm configuration, run pending migrations and restart the workload.

12. [`ingress_revoked`](https://github.com/canonical/traefik-k8s-operator): fired when the ingress for the web app is not ready anymore. **Action**: validate the charm configuration, run pending migrations and restart the workload.

13. [`rotate_secret_key`](https://documentation.ubuntu.com/juju/latest/user/reference/action/): fired when secret-rotate is executed.  **Action**: generate a new secret token for the application.

14. [`redeliver_failed_webhooks_action`](https://documentation.ubuntu.com/juju/latest/reference/action/): fired when the redeliver-failed-webhooks action is run. **Action**: Redeliver failed webhooks from GitHub.


> See more in the Juju docs: [Hook](https://documentation.ubuntu.com/juju/latest/reference/hook/)

## Charm code overview

The `src/charm.py` is the default entry point for a charm and has the `FlaskCharm` Python class that inherits from `paas_charm.flask.Charm`, which internally uses `paas_charm.PaasCharm` and  `CharmBase`. `CharmBase` is the base class from which all charms are formed, defined by [Ops](https://ops.readthedocs.io/en/latest/) (Python framework for developing charms).

> See more in the Juju docs: [Charm](https://documentation.ubuntu.com/juju/latest/reference/charm/)

The `__init__` method guarantees that the charm observes all events relevant to its operation and handles them.

Take, for example, when a configuration is changed by using the CLI.

1. User runs the configuration command:
```bash
juju config github-runner-webhook-router log-level=DEBUG
```
2. A `config-changed` event is emitted.
3. In the `__init__` method is defined how to handle this event like this:
```python
self.framework.observe(self.on.config_changed, self._on_config_changed)
```
4. The method `_on_config_changed`, for its turn, will take the necessary actions such as waiting for all the relations to be ready and then configuring the containers.
