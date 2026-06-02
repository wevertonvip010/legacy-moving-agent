import os
import logging
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins="*")

# Registrar blueprints
from webhooks.whatsapp import whatsapp_bp
app.register_blueprint(whatsapp_bp, url_prefix='/webhook')

@app.route('/health', methods=['GET'])
def health():
      return {'status': 'ok', 'service': 'legacy-moving-agent'}, 200

if __name__ == '__main__':
      port = int(os.environ.get('PORT', 5001))
      logger.info(f'Legacy Moving Agent rodando na porta {port}')
      app.run(host='0.0.0.0', port=port, debug=False)
  
