API Reference
=============

The extraction pipeline is organised into eight modules. The diagram below
shows the data flow:

.. code-block:: text

   hf_loader  ──►  normalize  ──►  extractor  ──►  main
                                       │
                              github_client  (GraphQL metadata)
                                       │
                                   git_ops    (local merge simulation)
                                       │
                                    schema    (PRRow dataclass)
                                   config     (environment settings)

.. toctree::
   :maxdepth: 1

   main
   extractor
   git_ops
   github_client
   hf_loader
   normalize
   schema
   config
