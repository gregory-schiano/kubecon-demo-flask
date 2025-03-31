# kubecon-demo-flask
A sample flask application using FFmpeg as a demo for Rockcraft at Kubecon


# Before demo
- Pull https://github.com/canonical/ssbom/pull/1

Run: `go build ./cmd/ssbom/`

- Install Rockcraft from `edge/pro-sources` channel

Run: `sudo snap install rockcraft --channel edge/pro-sources`

- Ensure your host is pro enabled
Run: `pro status`

# Demo

Start from this project's folder
```bash
ls -lah
vi app.py
cat requirements.txt
source .venv/bin/activate
flask run -p 8000
```

Open a browser on: http://127.0.0.1:8000

Show the application, you can use the following Youtube URL: https://www.youtube.com/watch?v=q5yM4ZYwB_s

Back to the terminal:
```bash
deactivate
rockcraft init --profile flask-framework
```

Edit rockcraft.yaml and apply the following changes:
- Base ubuntu@24.04
- Summary: A simple Flask application that uses python3-qrcode package
- Description:
```
  A simple Flask application meant to demo Flask 12-factor experience
  in Rockcraft, along with bare base / chiseled package and pro
  feature in Rockcraft
```
- Uncomment `parts:`
- Add `ffmpeg` in `runtime-debs`
- Add:
```yaml
  fix-symlinks:
    plugin: nil
    after: [runtime-debs]
    override-prime: |
      cd ${CRAFT_PRIME}/usr/lib/x86_64-linux-gnu/
      ln -sf blas/libblas.so.3 ${CRAFT_PRIME}/usr/lib/x86_64-linux-gnu/libblas.so.3
      ln -sf lapack/liblapack.so.3 ${CRAFT_PRIME}/usr/lib/x86_64-linux-gnu/liblapack.so.3
```
- Save & exit
```bash
rockcraft pack
sudo rockcraft.skopeo --insecure-policy copy oci-archive:kubecon-demo_0.1_amd64.rock docker-daemon:kubecon-demo:0.1
docker run --rm -d -p 8000:8000 --name kubecon-demo kubecon-demo:0.1
```

Open a browser on: http://127.0.0.1:8000

Show the application, you can use the following Youtube URL: https://www.youtube.com/watch?v=q5yM4ZYwB_s

Back to the terminal:
```bash
docker stop kubecon-demo
```

Edit rockcraft.yaml and do the following change:
- Version `0.2`
- Save & exit
```bash
rockcraft clean
pro status
sudo rockcraft pack --pro=esm-apps,esm-infra
sudo rockcraft.skopeo --insecure-policy copy oci-archive:kubecon-demo_0.2_amd64.rock docker-daemon:kubecon-demo:0.2
docker run --rm -d -p 8000:8000 --name kubecon-demo kubecon-demo:0.1
docker exec -ti kubecon-demo md5sum /usr/lib/x86_64-linux-gnu/libavcodec.so.60.31.102
docker stop kubecon-demo
docker run --rm -d -p 8000:8000 --name kubecon-demo kubecon-demo:0.2
docker exec -ti kubecon-demo md5sum /usr/lib/x86_64-linux-gnu/libavcodec.so.60.31.102
```

Open a browser on: http://127.0.0.1:8000

Show the application, you can use the following Youtube URL: https://www.youtube.com/watch?v=q5yM4ZYwB_s

Back to the terminal:
```bash
docker stop kubecon-demo
```

Edit rockcraft.yaml and do the following changes:
- Version `0.3`
- Base `bare`
- Add `build-base: ubuntu@24.04`
- Uncomment `runtime-slices` part
- Add:
```yaml
- base-files_chisel
- base-files_release-info
```
- Save & exit
```bash
rockcraft pack --pro=esm-apps,esm-infra
ls -lah kubecon-demo_0.*
sudo rockcraft.skopeo --insecure-policy copy oci-archive:kubecon-demo_0.3_amd64.rock docker-daemon:kubecon-demo:0.3
docker run --rm -d -p 8000:8000 --name kubecon-demo kubecon-demo:0.3
```

Open a browser on: http://127.0.0.1:8000

Show the application, you can use the following Youtube URL: https://www.youtube.com/watch?v=q5yM4ZYwB_s

Back to the terminal:
```bash
docker stop kubecon-demo
```

# Show vulnerability scan

Create a file in /tmp/trivy.tpl with the following content:
```
{{- $critical := 0 }}
{{- $high := 0 }}
{{- $medium := 0 }}
{{- $low := 0}}
{{- range . }}
  {{- range .Vulnerabilities }}
    {{- if  eq .Severity "CRITICAL" }}
      {{- $critical = add $critical 1 }}
    {{- end }}
    {{- if  eq .Severity "HIGH" }}
      {{- $high = add $high 1 }}
    {{- end }}
    {{- if  eq .Severity "MEDIUM" }}
      {{- $medium = add $medium 1 }}
    {{- end }}
    {{- if  eq .Severity "LOW" }}
      {{- $low = add $low 1 }}
    {{- end }}
  {{- end }}
{{- end }}
Critical: {{ $critical }}
High: {{ $high }}
Medium: {{ $medium }}
Low: {{ $low }}
```

Run Trivy scan on initial image:
```bash
docker run -v /var/run/docker.sock:/var/run/docker.sock -v /tmp/trivy.tpl:/tmp/trivy.tpl -v $PWD/.trivyignore:/tmp/.trivyignore aquasec/trivy image -q --ignorefile /tmp/.trivyignore --scanners vuln --format template --template "@/tmp/trivy.tpl" kubecon-demo:0.1
```

Run trivy scan on the pro enabled image (requires ssbom as it's a bare image):
```bash
docker run --rm -d -p 8000:8000 --name kubecon-demo kubecon-demo:0.3
docker cp *Path to ssbom project*/ssbom kubecon-demo:/tmp
docker exec -ti kubecon-demo bash
cd
/tmp/ssbom /
exit
docker cp kubecon-demo:/var/lib/pebble/default/manifest.spdx.json .
docker run -v $PWD/manifest.spdx.json:/tmp/manifest.spdx.json -v /tmp/trivy.tpl:/tmp/trivy.tpl -v $PWD/.trivyignore:/tmp/.trivyignore aquasec/trivy sbom -q --ignorefile /tmp/.trivyignore --scanners vuln --format template --template "@/tmp/trivy.tpl" /tmp/manifest.spdx.json
```
