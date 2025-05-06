# Github Runner Webhook Router Operator

A Juju charm deploying and managing a simple Flask application that listens for incoming webhooks
from GitHub and places a translation of those in a message queue for a runner to pick up and process.
It is intended to be used together with the [Github runner operator](https://charmhub.io/github-runner) 
in reactive mode.

This charm simplifies initial deployment and "day N" operations of
the application on Kubernetes. It allows for deployment on many
different Kubernetes platforms, from [MicroK8s](https://microk8s.io)
to [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud
Kubernetes offerings.

For DevOps or SRE teams this charm will make operating the Flask application simple
and straightforward through Juju's clean interface. It will allow easy
deployment into multiple environments for testing of changes.

The charm integrates with the [Canonical Observability Stack](https://charmhub.io/topics/canonical-observability-stack)
to provide application and Flask related metrics via Grafana dashboards.

## Contributing to this documentation

Documentation is an important part of this project, and we take the
same open-source approach to the documentation as the code. As such,
we welcome community contributions, suggestions and constructive
feedback on our documentation. Our documentation is hosted on the
[Charmhub forum](https://discourse.charmhub.io/) to enable easy
collaboration. Please use the “Help us improve this documentation”
links on each documentation page to either directly change something
you see that’s wrong, or ask a question, or make a suggestion about a
potential change via the comments section.

If there’s a particular area of documentation that you’d like to see that’s
missing, please [file a bug](https://github.com/canonical/github-runner-webhook-router/issues).


## Project and community

The Github Runner Webhook Router Operator is a member of the Ubuntu family. It's an open-source project that warmly welcomes community
projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](https://github.com/canonical/hockeypuck-k8s-operator/blob/main/CONTRIBUTING.md)

Thinking about using the Github Runner Webhook Router Operator for your next project?
[Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!
