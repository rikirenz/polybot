"""
=============================================================================
STEP 4: MODEL TRAINING
=============================================================================

WHY XGBOOST:

1. Handles tabular data extremely well — consistently wins Kaggle competitions
   on structured/tabular data (which is what trading features are).

2. Built-in feature importance — tells you WHICH features drive predictions.
   This is critical for a trading system: you need to understand WHY the model
   is making a decision, not just what the decision is.

3. Fast training — minutes, not hours. Important for iteration speed.

4. Handles missing values natively — robust to messy real-world data.

5. Regularization built-in — less prone to overfitting than random forests
   on small datasets.

WHY NOT deep learning?
- Our feature set is small (6 features) and tabular
- We have ~2000 samples — deep learning needs 10-100x more
- XGBoost is more interpretable
- Simpler to deploy and debug

TRAIN/TEST SPLIT:
We use TIME-BASED splitting (not random). Why? Because in trading, you always
train on the past and predict the future. Random splitting would leak future
information into training (look-ahead bias).
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report
)
from monitoring import get_logger
from config import TEST_SIZE, RANDOM_STATE

logger = get_logger("Model")

# Features used by the model
FEATURE_COLS = [
    "momentum",
    "rolling_volume",
    "rolling_volatility",
    "volume_momentum",
    "price_zscore",
]


def train_model(df: pd.DataFrame, feature_cols: list[str] = None) -> tuple[XGBClassifier, pd.DataFrame, pd.DataFrame]:
    """
    Train XGBoost classifier with time-based train/test split.
    
    Returns: (trained_model, test_dataframe, feature_importance_df)
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS

    logger.info(f"Training model on {len(df)} samples, {len(feature_cols)} features")

    # --- Time-based split (NOT random — critical for trading) ---
    split_idx = int(len(df) * (1 - TEST_SIZE))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    logger.info(
        f"Split: train={len(train_df)} samples (timestamps 0-{split_idx}), "
        f"test={len(test_df)} samples (timestamps {split_idx}-{len(df)})"
    )

    X_train = train_df[feature_cols]
    y_train = train_df["label"]
    X_test = test_df[feature_cols]
    y_test = test_df["label"]

    # --- Model configuration ---
    model = XGBClassifier(
        n_estimators=100,          # Number of trees
        max_depth=4,               # Shallow trees = less overfitting
        learning_rate=0.1,         # Standard learning rate
        subsample=0.8,             # Row sampling (regularization)
        colsample_bytree=0.8,     # Column sampling (regularization)
        random_state=RANDOM_STATE,
        eval_metric="logloss",
        verbosity=0,
    )

    # --- Train ---
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # --- Predictions ---
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    test_df["prediction_proba"] = y_pred_proba
    test_df["prediction"] = y_pred

    # --- Evaluation Metrics ---
    # Handle edge case where test set has only one class
    unique_classes = y_test.nunique()
    roc_auc = float("nan")
    if unique_classes > 1:
        roc_auc = roc_auc_score(y_test, y_pred_proba)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc,
    }

    logger.info("=== Model Evaluation ===")
    for metric, value in metrics.items():
        logger.info(f"  {metric}: {value:.4f}")

    # --- Feature Importance ---
    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    logger.info(f"\n=== Feature Importance ===\n{importance.to_string(index=False)}")

    # --- Classification Report ---
    present_labels = sorted(y_test.unique())
    label_names = {0: "HOLD", 1: "BUY"}
    target_names = [label_names[l] for l in present_labels]
    logger.info(
        f"\n=== Classification Report ===\n"
        f"{classification_report(y_test, y_pred, labels=present_labels, target_names=target_names)}"
    )

    return model, test_df, importance


if __name__ == "__main__":
    from data_ingestion import generate_simulated_data
    from feature_engineering import engineer_features
    from labels import create_labels

    df = generate_simulated_data()
    df = engineer_features(df)
    df = create_labels(df)
    model, test_df, importance = train_model(df)

    print("\n=== Feature Importance ===")
    print(importance.to_string(index=False))
