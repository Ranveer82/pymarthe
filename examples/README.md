

Description :memo:
-----------------------------------------------

Welcome to PyMarthe's `examples` section. Here you'll find in the following folders some pre-run reference **MARTHE** models:<br>

&emsp;&emsp;⫸&nbsp;_`monav3/`_ (**Mo**del **N**ord **A**quitain, _version 3_)<br>
&emsp;&emsp;⫸&nbsp;_`lizonnev2/`_ (**MONA** refined extraction of Lizonne river with _soil_ and _pumping_ property)<br>
&emsp;&emsp;⫸&nbsp;_`hallue/`_ (local model for _pumping optimisation_ purpose)<br>
&emsp;&emsp;⫸&nbsp;_`didac3/`_ (**MARTHE** tutorial model _n°3_)<br>

In this section you'll also find **2 coding guides** in the form of `jupyter notebook`:

&emsp;&emsp;⫸&nbsp;_`Basic_usage.ipynb`_ : ultimate guide to learn how to deal with **MARTHE** files, properties, grid geometry, field, outputs...<br>
&emsp;&emsp;⫸&nbsp;_`Advance_usage.ipynb`_ : ultimate guide to learn how to deal interface **MARTHE** and **PEST** algorithms.<br>

<br>

Launch Guides :rocket:
-----------------------------------------------

The provided guides are indexed in **sections** and **subsections** to facilitate their exploration. To take full advantage, make sure to install the `jupyter nbextension`:

_Via pip_
```shell
pip install jupyter_contrib_nbextensions
```

_Via conda_
```shell
conda install -c conda-forge jupyter_contrib_nbextensions
```

Then, to launch a guide, consider using:

```shell
jupyter notebook Basic_usage.ipynb
```

<br>

Write model inputs from a config file :pencil2:
-----------------------------------------------

The `model_inputs.yaml` file is a small, documented example showing how to set
values on the model **grids** (`MartheField` : `permh`, `emmca`, ...) and
**lists** (`MarthePump` : `aqpump`, `rivpump` ; `MartheSoil` : `soil`) from a
single YAML (or JSON) configuration file, and write them back into the MARTHE
input files &mdash; no python needed:

```shell
python ../scripts/write_model_inputs.py model_inputs.yaml
# equivalently:
python -m pymarthe.helpers.model_inputs model_inputs.yaml
```

From python:

```python
from pymarthe.helpers.model_inputs import write_model_inputs
mm = write_model_inputs('model_inputs.yaml')
```
