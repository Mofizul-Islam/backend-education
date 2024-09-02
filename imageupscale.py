# import cv2

# def blur_image(image_path, blur_type='gaussian', kernel_size=5):
#     # Read the image
#     img = cv2.imread(image_path)

#     # Check if image is loaded successfully
#     if img is None:
#         print("Error: Image not found!")
#         return

#     # Apply the specified blur
#     if blur_type == 'gaussian':
#         blurred_img = cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)
#     elif blur_type == 'median':
#         blurred_img = cv2.medianBlur(img, kernel_size)
#     elif blur_type == 'bilateral':
#         blurred_img = cv2.bilateralFilter(img, kernel_size, sigmaColor=75, sigmaSpace=75)
#     else:
#         print("Error: Invalid blur type specified!")
#         return

#     # Save the blurred image
#     output_path = f"blurred_{blur_type}_{image_path}"
#     cv2.imwrite(output_path, blurred_img)

#     print(f"Blurred image saved as: {output_path}")

# # Example usage
# image_path = "example.jpg"
# blur_image(image_path, blur_type='gaussian', kernel_size=5)

print("image upscale")