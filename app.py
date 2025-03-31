import io
import os
import ffmpeg
from flask import Flask, request, Response, jsonify, send_file
import yt_dlp


app = Flask(__name__)

VIDEO_PATH = 'static/video.mp4'

class ProbeError(Exception):
    pass


def get_video_path(video_id: str = None) -> str | None:
    """
    Returns the file path of the video to use.
    If video_id is provided, it returns 'static/cached_{video_id}.mp4'
    if that file exists; otherwise, returns None.
    If no video_id is provided, returns the default video path.
    """
    if not video_id:
        return VIDEO_PATH
    
    path = f"static/cache/cached_{video_id}.mp4"
    if os.path.exists(path):
        return path
    else:
        return None

def get_video_metadata(video_path: str) -> dict:
    """
    Retrieves metadata from the video using ffmpeg.probe.
    Returns a dictionary containing:
      - codec
      - width
      - height
      - duration (in seconds)
      - framerate (in images per second)
    """
    probe = ffmpeg.probe(video_path)
    video_stream = next(
        (stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
        None
    )
    if not video_stream:
        raise ProbeError('No video stream found')
    codec = video_stream.get('codec_name', 'unknown')
    width = int(video_stream.get('width', 0))
    height = int(video_stream.get('height', 0))
    duration = float(probe['format']['duration'])
    # r_frame_rate is usually a string like "25/1". Compute the fps.
    r_frame_rate = video_stream.get('r_frame_rate', '0/0')
    num, den = r_frame_rate.split('/')
    framerate = float(num) / float(den) if float(den) != 0 else 0.0
    return {
        'codec': codec,
        'width': width,
        'height': height,
        'duration': duration,
        'framerate': framerate
    }


@app.route('/metadata')
def metadata():
    """
    Returns video metadata in JSON format.
    """
    video_id = request.args.get("video_id", None)
    video_path = get_video_path(video_id)
    if video_id and video_path is None:
        return jsonify({'error': f'Cached video not found for video_id {video_id}'}), 404

    try:
        meta = get_video_metadata(video_path)
    except ProbeError as exc:
        return jsonify({'error': 'Unable to retrieve video metadata', 'message': str(exc)}), 500
    return jsonify(meta)


@app.route('/thumbnail')
def thumbnail():
    """
    Generates a thumbnail from VIDEO_PATH at a timestamp (in seconds)
    provided via the 'timestamp' query parameter. Returns a PNG image.
    If the timestamp is missing or out of bounds, returns an error.
    """
    timestamp = request.args.get('timestamp', type=float)
    if timestamp is None:
        return jsonify({'error': 'Missing timestamp parameter'}), 400

    video_id = request.args.get("video_id", None)
    video_path = get_video_path(video_id)
    if video_id and video_path is None:
        return jsonify({'error': f'Cached video not found for video_id {video_id}'}), 404

    try:
        meta = get_video_metadata(video_path)
    except ProbeError as exc:
        return jsonify({'error': 'Unable to retrieve video metadata', 'message': str(exc)}), 500

    if timestamp < 0 or timestamp > meta['duration']:
        return jsonify({'error': 'Timestamp out of video duration bounds'}), 400

    try:
        # Use ffmpeg to seek to the timestamp and output one frame as PNG
        out, _ = (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output('pipe:', vframes=1, format='image2', vcodec='png')
            .run(capture_stdout=True, capture_stderr=True)
        )
        return Response(out, mimetype='image/png')
    except (ValueError, ffmpeg.Error) as exc:
        return jsonify({'error': 'Error generating thumbnail', 'details': str(exc)}), 500


@app.route('/video')
def serve_video():
    """
    Serves the video file.
    If a 'video_id' query parameter is provided, serves the cached video;
    otherwise, serves the default static video.
    """
    video_id = request.args.get("video_id", None)
    video_path = get_video_path(video_id)
    if video_id and video_path is None:
        return jsonify({'error': f'Cached video not found for video_id {video_id}'}), 404
    return send_file(video_path, mimetype='video/mp4')


@app.route('/set_video', methods=['POST'])
def set_video():
    """
    Sets the current video to a YouTube video.
    Expects a JSON payload with a 'youtube_url' field.
    Downloads the video, caches it as 'static/cache/cached_{video_id}.mp4',
    and returns the video_id.
    """
    youtube_url = request.json.get("youtube_url")
    if not youtube_url:
        return jsonify({'error': 'No YouTube URL provided'}), 400
    try:
        # Configure yt-dlp options:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',  # dynamically select best available streams
            'merge_output_format': 'mp4',           # merge into mp4 format
            'outtmpl': 'static/cache/cached_%(id)s.%(ext)s',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
        video_id = info.get('id')
        if not video_id:
            return jsonify({'error': 'Unable to extract video id'}), 400
        return jsonify({'message': 'Video updated successfully', 'video_id': video_id})
    except yt_dlp.utils.YoutubeDLError as exc:
        return jsonify({'error': 'Error downloading video', 'details': str(exc)}), 500

@app.route('/')
def index():
    """
    Serves an HTML page that:
      - Provides a field to set a YouTube video.
      - Embeds the video via the /video endpoint.
      - Displays a slider to choose a timestamp (auto-updating the thumbnail).
      - Shows video metadata in a nicely formatted Bootstrap card.
      - On page load, initializes the slider to a random timestamp.
    If no YouTube video is set, the static video is used.
    """
    html_content = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Video Thumbnail and Metadata Viewer</title>
      <!-- Bootstrap CSS -->
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { padding-top: 2rem; }
        #thumbnail { max-width: 100%; border: 1px solid #ccc; }
        #overlaySpinner {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(255,255,255,0.8);
          z-index: 1050; /* Ensure it sits on top of other content */
          display: flex;
          align-items: center;
          justify-content: center;
        }
      </style>
    </head>
    <body>
      <div id="overlaySpinner" style="display:none;">
        <div class="spinner-border text-primary" role="status" style="width: 4rem; height: 4rem;">
          <span class="visually-hidden">Loading...</span>
        </div>
      </div>
      <div class="container">
        <header class="mb-4">
          <h1 class="text-center">Video Thumbnail and Metadata Viewer</h1>
        </header>
        <div class="card mb-4">
          <div class="card-header">Set YouTube Video</div>
          <div class="card-body">
            <div class="mb-3">
              <label for="youtubeUrl" class="form-label">YouTube URL:</label>
              <input type="text" class="form-control" id="youtubeUrl" placeholder="Enter YouTube URL">
            </div>
            <button class="btn btn-primary" onclick="setYouTubeVideo()">Set Video</button>
            <button class="btn btn-primary" onclick="setDefaultVideo()">Default Video</button>
            <p id="setVideoError" class="text-danger mt-2"></p>
          </div>
        </div>
        <div class="row">
          <div class="col-md-8">
            <div class="card mb-4">
              <div class="card-body">
                <video id="videoPlayer" class="w-100" controls>
                  <source src="/video" type="video/mp4">
                  Your browser does not support the video tag.
                </video>
              </div>
            </div>
          </div>
          <div class="col-md-4">
            <div class="card mb-4">
              <div class="card-header">Video Metadata</div>
              <div class="card-body" id="metaInfo">
                Loading metadata...
              </div>
            </div>
            <div class="card mb-4">
              <div class="card-header">Generate Thumbnail</div>
              <div class="card-body">
                <div class="mb-3">
                  <label for="timestamp" class="form-label">Timestamp (seconds): <span id="timestampValue">0</span></label>
                  <input type="range" class="form-range" id="timestamp" name="timestamp" min="0" max="100" value="0" step="0.1" oninput="updateThumbnail(this.value)">
                </div>
                <div class="mb-3">
                  <img id="thumbnail" src="" alt="Thumbnail will appear here" class="img-fluid">
                  <p id="error" class="text-danger mt-2"></p>
                </div>
              </div>
            </div>
          </div>
          </div>
        </div>
      </div>
      <!-- Bootstrap JS Bundle -->
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
      <script>
        // Global variable to keep track of the current video_id.
        // An empty string means the default static video.
        var currentVideoId = "";

        function updateThumbnail(val) {
          document.getElementById('timestampValue').innerText = val;
          let url = '/thumbnail?timestamp=' + val;
          if(currentVideoId) {
            url += '&video_id=' + currentVideoId;
          }
          fetch(url)
            .then(response => {
              if (!response.ok) {
                return response.json().then(err => { throw err; });
              }
              return response.blob();
            })
            .then(blob => {
              const url = URL.createObjectURL(blob);
              document.getElementById('thumbnail').src = url;
              document.getElementById('error').innerText = "";
            })
            .catch(err => {
              document.getElementById('error').innerText = err.error || "Error generating thumbnail";
            });
        }

        function loadMetadata() {
          let url = '/metadata';
          if(currentVideoId) {
            url += '?video_id=' + currentVideoId;
          }
          fetch(url)
            .then(response => response.json())
            .then(data => {
              const metaInfo = `<strong>Codec:</strong> ${data.codec}<br>
                                <strong>Resolution:</strong> ${data.width} x ${data.height}<br>
                                <strong>Duration:</strong> ${data.duration.toFixed(2)} seconds<br>
                                <strong>Framerate:</strong> ${data.framerate.toFixed(2)} fps`;
              document.getElementById('metaInfo').innerHTML = metaInfo;
              let currentTimestamp = parseFloat(document.getElementById('timestamp').value);
              if(currentTimestamp > data.duration) {
                  currentTimestamp = (Math.random() * data.duration).toFixed(1);
                  document.getElementById('timestamp').value = currentTimestamp;
                  document.getElementById('timestampValue').innerText = currentTimestamp;
              }
              document.getElementById('timestamp').max = data.duration;
              updateThumbnail(document.getElementById('timestamp').value);
            })
            .catch(err => {
              document.getElementById('metaInfo').innerText = "Error loading metadata";
            });
        }

        function setYouTubeVideo() {
          const youtubeUrl = document.getElementById('youtubeUrl').value;
          document.getElementById('overlaySpinner').style.display = 'flex';
          fetch('/set_video', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ youtube_url: youtubeUrl })
          })
          .then(response => response.json())
          .then(data => {
            if(data.error) {
              document.getElementById('setVideoError').innerText = data.error;
            } else {
              document.getElementById('setVideoError').innerText = "";
              // Update the global video id and refresh the video player source.
              currentVideoId = data.video_id;
              document.getElementById('videoPlayer').innerHTML =
                '<source src="/video?video_id=' + currentVideoId + '" type="video/mp4">';
              document.getElementById('videoPlayer').load();
              loadMetadata();
            }
          })
          .catch(err => {
            document.getElementById('setVideoError').innerText = "Error setting video";
          })
          .finally(() => {
            // Hide the spinner when done
            document.getElementById('overlaySpinner').style.display = 'none';
          });
        }

        function setDefaultVideo() {
          currentVideoId = '';
          document.getElementById('videoPlayer').innerHTML = '<source src="/video" type="video/mp4">';
          document.getElementById('videoPlayer').load();
          document.getElementById('youtubeUrl').value = "";
          loadMetadata();
        }

        // On page load, initialize metadata and set a random timestamp.
        window.addEventListener('DOMContentLoaded', function() {
          loadMetadata();
        });
      </script>
    </body>
    </html>
    '''
    return Response(html_content, mimetype='text/html')


if __name__ == "__main__":
    app.run(debug=True)

