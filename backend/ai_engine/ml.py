import math


def _softmax(values):
    maximum = max(values) if values else 0.0
    exponents = [math.exp(value - maximum) for value in values]
    total = sum(exponents) or 1.0
    return [value / total for value in exponents]


def _standardize(rows, means=None, scales=None):
    if not rows:
        return [], [], []
    width = len(rows[0])
    if means is None:
        means = [sum(row[index] for row in rows) / len(rows) for index in range(width)]
    if scales is None:
        scales = []
        for index in range(width):
            variance = sum((row[index] - means[index]) ** 2 for row in rows) / len(rows)
            scales.append(math.sqrt(variance) or 1.0)
    transformed = [
        [(row[index] - means[index]) / scales[index] for index in range(width)]
        for row in rows
    ]
    return transformed, means, scales


def train_logistic_regression(rows, labels, classes, epochs=700, learning_rate=0.08, l2=0.01):
    if not rows or len(rows) != len(labels):
        raise ValueError("Training features and labels are required.")
    transformed, means, scales = _standardize(rows)
    width = len(transformed[0])
    weights = [[0.0] * width for _ in classes]
    biases = [0.0] * len(classes)
    label_indexes = [classes.index(label) for label in labels]
    label_counts = {label: labels.count(label) for label in classes}
    example_weights = [len(labels) / (len(classes) * label_counts[label]) for label in labels]

    for _ in range(epochs):
        weight_gradients = [[0.0] * width for _ in classes]
        bias_gradients = [0.0] * len(classes)
        total_weight = sum(example_weights) or 1.0
        for row, expected, example_weight in zip(transformed, label_indexes, example_weights):
            probabilities = _softmax([
                biases[class_index] + sum(weight * value for weight, value in zip(weights[class_index], row))
                for class_index in range(len(classes))
            ])
            for class_index in range(len(classes)):
                error = (probabilities[class_index] - (1.0 if class_index == expected else 0.0)) * example_weight
                bias_gradients[class_index] += error
                for feature_index, value in enumerate(row):
                    weight_gradients[class_index][feature_index] += error * value
        for class_index in range(len(classes)):
            biases[class_index] -= learning_rate * bias_gradients[class_index] / total_weight
            for feature_index in range(width):
                gradient = weight_gradients[class_index][feature_index] / total_weight
                gradient += l2 * weights[class_index][feature_index]
                weights[class_index][feature_index] -= learning_rate * gradient

    return {
        "classes": list(classes),
        "means": means,
        "scales": scales,
        "weights": weights,
        "biases": biases,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "l2": l2,
    }


def predict_probabilities(parameters, row):
    classes = list(parameters.get("classes") or [])
    means = list(parameters.get("means") or [])
    scales = list(parameters.get("scales") or [])
    weights = list(parameters.get("weights") or [])
    biases = list(parameters.get("biases") or [])
    if not classes or len(row) != len(means) or len(means) != len(scales):
        raise ValueError("The model feature schema does not match this project analysis.")
    transformed = [(value - means[index]) / (scales[index] or 1.0) for index, value in enumerate(row)]
    logits = [
        biases[class_index] + sum(weight * value for weight, value in zip(weights[class_index], transformed))
        for class_index in range(len(classes))
    ]
    probabilities = _softmax(logits)
    return {label: probability for label, probability in zip(classes, probabilities)}


def evaluate_model(parameters, rows, labels):
    if not rows:
        return {"sample_count": 0, "accuracy": None, "confusion_matrix": {}}
    classes = list(parameters.get("classes") or [])
    confusion = {label: {predicted: 0 for predicted in classes} for label in classes}
    correct = 0
    for row, expected in zip(rows, labels):
        probabilities = predict_probabilities(parameters, row)
        predicted = max(probabilities, key=probabilities.get)
        confusion.setdefault(expected, {label: 0 for label in classes})
        confusion[expected][predicted] = confusion[expected].get(predicted, 0) + 1
        correct += int(predicted == expected)
    return {
        "sample_count": len(rows),
        "accuracy": round(correct / len(rows), 4),
        "confusion_matrix": confusion,
    }


def feature_contributions(parameters, row, feature_names, predicted_class, limit=5):
    classes = list(parameters.get("classes") or [])
    if predicted_class not in classes:
        return []
    class_index = classes.index(predicted_class)
    means = list(parameters.get("means") or [])
    scales = list(parameters.get("scales") or [])
    weights = list(parameters.get("weights") or [])[class_index]
    values = []
    for index, name in enumerate(feature_names):
        standardized = (row[index] - means[index]) / (scales[index] or 1.0)
        contribution = standardized * weights[index]
        values.append({"feature": name, "contribution": round(contribution, 4)})
    values.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return values[:limit]
