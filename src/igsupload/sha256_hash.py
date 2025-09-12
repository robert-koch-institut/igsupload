import base64
import re
import hashlib

def create_hash(file_path):
  sha256 = hashlib.sha256()
  with open(file_path, "rb") as f:
    while chunk := f.read(8192): # 8192 = 8 kb more efficiant
      sha256.update(chunk)
  return sha256.hexdigest()

