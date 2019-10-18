Clients
=======

A REST client is available for interacting with Patchwork's API, and other
projects build on top of the API to provide other functionality.


git-pw
------

The :program:`git-pw` application can be used to integrate Git with Patchwork.
The :program:`git-pw` application relies on the REST API and can be used to
interact to list, download and apply series, bundles and individual patches.

More information on :program:`git-pw`, including installation and usage
instructions, can be found in the `documentation`__ and the `GitHub repo`__.

__ https://git-pw.readthedocs.io/
__ https://github.com/getpatchwork/git-pw/


snowpatch
---------

The :program:`snowpatch` application is a bridge between Patchwork and the
Jenkins continuous integration automation server. It monitors the REST API
for incoming patches, applies them on top of an existing git tree, triggers
appropriate builds and test suites, and reports the results back to Patchwork.

Find out more about :program:`snowpatch` at its `GitHub repo`__.

__ https://github.com/ruscur/snowpatch
