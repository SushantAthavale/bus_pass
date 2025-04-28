-- Update QR code paths
UPDATE bus_passes 
SET qr_code = 'qr_codes/' || qr_code 
WHERE qr_code NOT LIKE 'qr_codes/%';
 
-- Update image paths
UPDATE bus_passes 
SET image_path = 'user_images/' || image_path 
WHERE image_path IS NOT NULL AND image_path NOT LIKE 'user_images/%'; 