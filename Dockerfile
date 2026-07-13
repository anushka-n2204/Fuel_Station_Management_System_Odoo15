FROM --platform=linux/amd64 odoo:15.0

USER root

# Install python3-pip and xlsxwriter (required for Excel exports)
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip && \
    pip3 install --no-cache-dir xlsxwriter && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER odoo
