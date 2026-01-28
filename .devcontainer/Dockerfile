FROM python:3.12-slim-bookworm

WORKDIR /workspace

# Install from pre-built wheel to get dependencies and accelerator
COPY dist/ /tmp/dist/
RUN pip install --no-cache-dir /tmp/dist/*.whl && \
    pip uninstall -y surrealengine && \
    rm -rf /tmp/dist

# Install JupyterLab explicitly since it's a dev dependency not in the wheel
RUN pip install --no-cache-dir jupyterlab notebook

# Set PYTHONPATH to use the mounted source code (edits reflect immediately)
# The source directory MUST contain the compiled .so extension for this to work
ENV PYTHONPATH="/workspace/src"

# Configure JupyterLab
COPY jupyter_lab_config.py /root/.jupyter/jupyter_lab_config.py


EXPOSE 8888
CMD ["jupyter", "lab", "--config=/root/.jupyter/jupyter_lab_config.py", "--allow-root"]