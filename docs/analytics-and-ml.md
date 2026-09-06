# Analytics and Machine Learning

## Purpose

The analytics layer turns assessment and engagement records into understandable performance views for students and lecturers. The machine-learning component provides broad performance profiles that can support targeted follow-up.

## Data sources

The main datasets are:

- `quiz_df`: quiz questions, attempts, scores, subtopics, and correctness
- `test_df`: test questions, scores, subtopics, and correctness
- Engagement data: learning-material viewing and related activity
- Learning materials: content used by the RAG pipeline

The current datasets are synthetic and are intended for development and demonstration.

## Key metrics

- Quiz performance by module and subtopic
- Test performance by module and subtopic
- Weighted score combining quiz and test results
- Number of quiz attempts
- Percentage of learning materials viewed
- Incorrect-question frequency
- Highest- and lowest-performing student lists

## Scoring logic

The project combines quiz and test performance using a weighted score:

```text
weighted score = 0.3 × quiz score + 0.7 × test score
```

Scores can be calculated at module, subtopic, student, or cohort level. The lecturer dashboard uses additional rules to highlight areas where fewer than 65% of questions are answered correctly and to identify questions missed by more than 25 students in the current dataset.

These thresholds are practical prototype choices, not universal academic standards.

## Data preparation pipeline

1. Aggregate quiz and test records by student, module, and subtopic.
2. Calculate subtopic-level performance from correct and incorrect answers.
3. Combine quiz and test results.
4. Create features for each module and assessment type.
5. Pivot the data so each student has one row and each performance measure is a feature.
6. Standardise the features before clustering.

Standardisation matters because K-Means uses distance. Without it, features with larger scales could influence the clusters more strongly than other features.

## K-Means clustering

### Objective

K-Means groups students with similar performance patterns across modules and assessment types. The groups are intended to support exploration and intervention planning, not to make final judgements about students.

### Selecting the number of clusters

The project uses an elbow plot to compare the sum of squared errors for different values of `k`. Four clusters were selected for the current dataset because the plot showed a useful reduction in error at that point.

### Current cluster interpretation

- **Cluster 0:** Stronger test performance in DAVA and DSES, with mixed quiz and module results.
- **Cluster 1:** Generally lower quiz and test performance across modules.
- **Cluster 2:** Better quiz performance than test performance across modules.
- **Cluster 3:** Stronger test performance in DWBI and LOMA, with mixed quiz and module results.

These labels describe the current synthetic dataset. They should be recalculated and reinterpreted when the data changes.

## Dashboards

### Student dashboard

Students can:

- View performance across modules
- Explore subtopic results
- Compare quiz and test outcomes
- Filter by quiz attempts
- Review learning-material viewing levels
- Connect performance patterns with AI-generated learning support

### Lecturer dashboard

Lecturers can:

- View cohort performance
- Compare modules and subtopics
- Inspect top- and bottom-performing students
- Identify common mistakes
- Review quiz-attempt patterns
- Compare performance with learning-material engagement
- Use AI summaries to plan targeted support

## Evaluation and interpretation

The project demonstrates descriptive analytics, interactive filtering, and student segmentation. It shows how performance data can help users find weak topics and decide where additional support may be useful.

The current work does not establish predictive accuracy. The clusters are exploratory profiles, and the dashboards show associations in the available data rather than proven causes of student performance.

## Limitations

- Synthetic records do not capture the full complexity of real student behaviour.
- K-Means clusters are descriptive and should not be treated as definitive risk predictions.
- The choice of four clusters depends on the current dataset and may change with new data.
- No labelled ground truth is available to confirm whether the clusters represent meaningful learner groups.
- Score thresholds can oversimplify understanding and may not transfer to other classes.
- Engagement metrics alone cannot explain why a student is struggling.
- Tableau and Streamlit provide useful views, but dashboard results still depend on the quality and freshness of the database data.

## Future improvements

- Add formal cluster-quality measures such as silhouette score.
- Compare K-Means with other clustering approaches.
- Add longitudinal progress and time-based features.
- Validate the metrics and thresholds with lecturers.
- Evaluate the system with approved, representative data.
- Add confidence indicators and clearer explanations for analytics-based recommendations.

[← Back to README](../README.md)
