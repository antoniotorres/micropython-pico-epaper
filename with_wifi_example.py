#!/usr/bin/env python

from micropython_epaper_display import EPaperDisplay
import network
import socket
import time
import json

def connect_wifi(ssid, password):
    # Create WLAN interface
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Connect to WiFi if not already connected
    if not wlan.isconnected():
        print(f'Connecting to WiFi network: {ssid}...')
        wlan.connect(ssid, password)
        
        # Wait for connection with timeout
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print('Waiting for connection...')
            time.sleep(1)
    
    if wlan.isconnected():
        print('WiFi connected successfully')
        print('Network config:', wlan.ifconfig())
        return True
    else:
        print('WiFi connection failed')
        return False

def start_webserver():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    
    print('Listening on', addr)
    
    # HTML with frontend image processing
    html = """<!DOCTYPE html>
    <html>
        <head>
            <title>E-Paper Display Control</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .container { max-width: 800px; margin: 0 auto; }
                .preview-container { display: flex; gap: 20px; margin: 20px 0; }
                .preview { flex: 1; }
                canvas { border: 1px solid #ccc; }
                .hidden { display: none; }
                #status { margin-top: 10px; padding: 10px; }
                .error { color: red; }
                .success { color: green; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>E-Paper Display Control</h1>
                <form id="uploadForm">
                    <input type="file" id="imageInput" accept="image/*" required>
                    <button type="submit">Upload and Display</button>
                </form>
                <div id="status"></div>
                <div class="preview-container">
                    <div class="preview">
                        <h3>Original:</h3>
                        <img id="imagePreview">
                    </div>
                    <div class="preview">
                        <h3>Processed (122x250 B&W):</h3>
                        <canvas id="processedPreview" width="122" height="250"></canvas>
                    </div>
                </div>
                <canvas id="tempCanvas" class="hidden"></canvas>
            </div>
            <script>
                const EPAPER_WIDTH = 122;
                const EPAPER_HEIGHT = 250;
                let processedImageData = null;
                
                function showStatus(message, isError = false) {
                    const status = document.getElementById('status');
                    status.textContent = message;
                    status.className = isError ? 'error' : 'success';
                }
                
                function processImage(originalImage) {
                    return new Promise((resolve) => {
                        // Create a temporary canvas for initial scaling and grayscale conversion
                        const tempCanvas = document.createElement('canvas');
                        tempCanvas.width = originalImage.width;
                        tempCanvas.height = originalImage.height;
                        const tempCtx = tempCanvas.getContext('2d');

                        // First draw original image and convert to grayscale
                        tempCtx.drawImage(originalImage, 0, 0);
                        const imageData = tempCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
                        const data = imageData.data;

                        // Convert to grayscale using simple averaging
                        for (let i = 0; i < data.length; i += 4) {
                            const avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
                            data[i] = data[i + 1] = data[i + 2] = avg;
                        }
                        tempCtx.putImageData(imageData, 0, 0);

                        // Now scale the grayscale image to e-paper dimensions
                        const processedCanvas = document.getElementById('processedPreview');
                        const processedCtx = processedCanvas.getContext('2d');

                        // Clear canvas with white background
                        processedCtx.fillStyle = 'white';
                        processedCtx.fillRect(0, 0, EPAPER_WIDTH, EPAPER_HEIGHT);

                        // Calculate scaling to fit the image properly
                        const scale = Math.min(
                            EPAPER_WIDTH / originalImage.width,
                            EPAPER_HEIGHT / originalImage.height
                        );

                        // Calculate dimensions and position to center the image
                        const newWidth = originalImage.width * scale;
                        const newHeight = originalImage.height * scale;
                        const x = (EPAPER_WIDTH - newWidth) / 2;
                        const y = (EPAPER_HEIGHT - newHeight) / 2;

                        // Draw the scaled grayscale image
                        processedCtx.drawImage(tempCanvas, x, y, newWidth, newHeight);

                        // Convert to pure black and white
                        const finalImageData = processedCtx.getImageData(0, 0, EPAPER_WIDTH, EPAPER_HEIGHT);
                        const finalData = finalImageData.data;

                        // Convert grayscale to binary format
                        const linewidth = Math.ceil(EPAPER_WIDTH / 8);
                        const binaryData = new Uint8Array(linewidth * EPAPER_HEIGHT);

                        // Pack bits into bytes - convert grayscale to binary (inverted)
                        for (let y = 0; y < EPAPER_HEIGHT; y++) {
                            for (let x = 0; x < EPAPER_WIDTH; x++) {
                                const i = (y * EPAPER_WIDTH + x) * 4;
                                const byteIndex = y * linewidth + Math.floor(x / 8);
                                const bitPosition = 7 - (x % 8);  // MSB first
                                
                                // Convert grayscale to binary (threshold at 128)
                                // Note: isBlack condition is inverted (> instead of <)
                                const isBlack = finalData[i] > 128;
                                
                                if (isBlack) {
                                    binaryData[byteIndex] |= (1 << bitPosition);
                                }
                            }
                        }

                        processedImageData = binaryData;
                        resolve(binaryData);
                    });
                }
                
                document.getElementById('imageInput').onchange = async function(e) {
                    const preview = document.getElementById('imagePreview');
                    const file = e.target.files[0];
                    
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            preview.src = e.target.result;
                            const img = new Image();
                            img.onload = async function() {
                                await processImage(img);
                                showStatus('Image processed and ready to upload');
                            };
                            img.src = e.target.result;
                        };
                        reader.readAsDataURL(file);
                    }
                };
                
                document.getElementById('uploadForm').onsubmit = async function(e) {
                    e.preventDefault();
                    
                    if (!processedImageData) {
                        showStatus('Please select and process an image first', true);
                        return;
                    }
                    
                    const submitButton = this.querySelector('button[type="submit"]');
                    submitButton.disabled = true;
                    showStatus('Uploading image to display...');
                    
                    try {
                        const response = await fetch('/display', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/octet-stream'
                            },
                            body: processedImageData
                        });
                        
                        let result;
                        try {
                            result = await response.json();
                        } catch (e) {
                            throw new Error('Invalid server response');
                        }
                        
                        if (!response.ok) {
                            throw new Error(result.message || `HTTP error! status: ${response.status}`);
                        }
                        
                        showStatus(result.message, !result.success);
                    } catch (error) {
                        showStatus('Error uploading image: ' + error.message, true);
                        console.error('Upload error:', error);
                    } finally {
                        submitButton.disabled = false;
                    }
                };
            </script>
        </body>
    </html>
    """
    
    while True:
        try:
            cl, addr = s.accept()
            print('Client connected from', addr)
            
            try:
                request = cl.recv(1024)
                request_str = request.decode('utf-8')
                
                # Handle POST request for display update
                if 'POST /display' in request_str:
                    print('Receiving display update request...')
                    
                    try:
                        # Find the content length
                        headers = request_str.split('\r\n\r\n')[0]
                        content_length = int([line for line in headers.split('\r\n') if 'Content-Length:' in line][0].split(': ')[1])
                        
                        # Read the binary data
                        body_start = request_str.find('\r\n\r\n') + 4
                        binary_data = bytearray(request[body_start:])
                        remaining = content_length - len(binary_data)
                        
                        while remaining > 0:
                            chunk = cl.recv(min(remaining, 1024))
                            if not chunk:
                                break
                            binary_data.extend(chunk)
                            remaining -= len(chunk)
                        
                        print(f'Received {len(binary_data)} bytes of image data')
                        
                        if len(binary_data) == content_length:
                            # Initialize and update e-paper display
                            epd = EPaperDisplay()
                            epd.init()
                            epd.display(binary_data)
                            
                            response = json.dumps({
                                'success': True,
                                'message': 'Image successfully displayed on e-Paper'
                            })
                            
                            response_headers = [
                                'HTTP/1.1 200 OK',
                                'Content-Type: application/json',
                                'Connection: keep-alive',
                                f'Content-Length: {len(response)}',
                                '',
                                ''
                            ]
                            cl.send('\r\n'.join(response_headers).encode())
                            cl.send(response.encode())
                            print('Display update successful')
                        else:
                            raise Exception('Incomplete data received')
                            
                    except Exception as e:
                        print('Error processing display update:', str(e))
                        response = json.dumps({
                            'success': False,
                            'message': f'Error updating display: {str(e)}'
                        })
                        response_headers = [
                            'HTTP/1.1 500 Internal Server Error',
                            'Content-Type: application/json',
                            'Connection: keep-alive',
                            f'Content-Length: {len(response)}',
                            '',
                            ''
                        ]
                        cl.send('\r\n'.join(response_headers).encode())
                        cl.send(response.encode())
                
                # Handle GET request for main page
                else:
                    # Encode the HTML content first
                    html_encoded = html.encode('utf-8')
                    
                    # Send response headers first
                    response_headers = [
                        'HTTP/1.1 200 OK',
                        'Content-Type: text/html; charset=utf-8',
                        'Connection: close',  # Changed to close
                        f'Content-Length: {len(html_encoded)}',
                        '',
                        ''
                    ]
                    
                    try:
                        # Send headers
                        cl.send('\r\n'.join(response_headers).encode('utf-8'))
                        
                        # Send content in chunks
                        chunk_size = 1024
                        for i in range(0, len(html_encoded), chunk_size):
                            chunk = html_encoded[i:i + chunk_size]
                            cl.send(chunk)
                            time.sleep(0.01)  # Small delay between chunks
                        
                        print(f'Sent {len(html_encoded)} bytes of HTML content')
                    except Exception as e:
                        print(f'Error sending response: {e}')
                
            except Exception as e:
                print('Error handling request:', str(e))
                error_response = json.dumps({
                    'success': False,
                    'message': f'Server error: {str(e)}'
                }).encode('utf-8')
                
                response_headers = [
                    'HTTP/1.1 500 Internal Server Error',
                    'Content-Type: application/json; charset=utf-8',
                    'Connection: close',
                    f'Content-Length: {len(error_response)}',
                    '',
                    ''
                ]
                
                try:
                    # Send error response in chunks too
                    cl.send('\r\n'.join(response_headers).encode('utf-8'))
                    cl.send(error_response)
                except:
                    pass
            
            finally:
                try:
                    time.sleep(0.1)  # Give time for data to be sent
                    cl.close()
                except:
                    pass
                
        except Exception as e:
            print('Server error:', str(e))
            try:
                cl.close()
            except:
                pass

def main():
    # Replace with your WiFi credentials
    SSID = "Casa"
    PASSWORD = "NoCompartir123!"
    
    if connect_wifi(SSID, PASSWORD):
        start_webserver()

if __name__ == "__main__":
    main()

