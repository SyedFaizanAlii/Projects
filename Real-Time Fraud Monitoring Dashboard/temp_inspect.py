import numpy as np
import pandas as pd
from data_pipeline import prepare_training_sample
from feature_store import extract_feature_columns
from model_ensemble import FraudModelEnsemble
from bias_mitigation import add_location_group

sample = prepare_training_sample(1000)
print('shape', sample.shape)
print('fraud rate', sample['is_fraud'].mean())
print('location group distribution', add_location_group(sample)['location_group'].value_counts(normalize=True).to_dict())
model = FraudModelEnsemble()
model.fit(sample)
print('trained', model.xgb_model is not None)
X = sample[extract_feature_columns()].astype(float)
probs = model.xgb_model.predict_proba(model.pipeline.transform(X))[:,1]
print('prob min max mean', probs.min(), probs.max(), probs.mean())
recon = model.autoencoder.predict(model.pipeline.transform(X), verbose=0)
recon_err = np.mean(np.square(model.pipeline.transform(X) - recon), axis=1)
print('recon err min max mean', recon_err.min(), recon_err.max(), recon_err.mean())
print('risk label counts >0.5 or >0.08', np.mean((probs>0.5) | (recon_err>0.08)))
print('fairness adjusted counts', np.bincount(model.calibrator.predict(model.pipeline.transform(X), sensitive_features=np.array(add_location_group(sample)['location_group']))))
