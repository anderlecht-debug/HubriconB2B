# Models

- `face_detection_yunet_2023mar.onnx`: OpenCV's YuNet face detector, used by
  `cv2.FaceDetectorYN` in the sourcing filters (VISUAL_SPEC.md §6.4) to reject any
  stock or AI candidate with a face over 1% of the frame. From
  https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet,
  fetched 2026-10-04, sha256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
  MIT licence, `YUNET-LICENSE.txt`.
