"""Stable public entry point for the selected CASE arousal model."""

from eurisko_arousal.model import calibrate_personal_model
from eurisko_arousal.selected_model import best_model_name, model

if __name__ == "__main__":
    example_features = {'mean_hr_z': 1.5,
     'hrv_sdnn_z': -0.3,
     'mean_scr_z': 1.1,
     'mean_resp_rate_z': 1.0,
     'skin_temp_sd_z': 0.2,
     'mean_hr_z_delta': 0.0,
     'hrv_sdnn_z_delta': 0.0,
     'mean_scr_z_delta': 0.0,
     'mean_resp_rate_z_delta': 0.0,
     'skin_temp_sd_z_delta': 0.0}
    prediction = model.predict(example_features)
    print(f"Predicted arousal: {prediction:.3f}")
