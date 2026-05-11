Installation
============

Requirements
------------

* Python 3.9 or later
* Git (must be on ``PATH``)
* One or more GitHub personal access tokens

Install dependencies
--------------------

Clone the repository and install Python dependencies:

.. code-block:: bash

   git clone https://github.com/unlv-evol/AgenticFlict.git
   cd AgenticFlict
   pip install -r requirements.txt

Configure environment
---------------------

Copy the example environment file and fill in your credentials:

.. code-block:: bash

   cp env-example.txt .env

Open ``.env`` and set at minimum:

.. code-block:: bash

   # One or more GitHub personal access tokens (comma-separated)
   GITHUB_TOKENS=ghp_your_token_here

   # HuggingFace token (only required for gated datasets)
   HF_TOKEN=hf_your_token_here

All other settings have sensible defaults. See :mod:`config` for a full
description of every available environment variable.

Verify setup
------------

.. code-block:: bash

   cd src
   python -c "from config import GITHUB_TOKENS; print('Tokens loaded:', len(GITHUB_TOKENS))"
