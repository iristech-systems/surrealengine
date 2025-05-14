FROM python:3.13-slim-bullseye

WORKDIR /surrealengine

# Install uv
RUN apt-get update && apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.cargo/bin/uv /usr/local/bin/uv

RUN mkdir -p notebooks

# Copy project files
COPY notebooks/ ./notebooks/
COPY src/ ./notebooks/src/
COPY example_scripts/ ./notebooks/examples/

# Set up virtual environment and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Configure JupyterLab
COPY jupyter_lab_config.py /root/.jupyter/jupyter_lab_config.py


EXPOSE 8888
CMD ["jupyter", "lab", "--config=/root/.jupyter/jupyter_lab_config.py", "--allow-root"]