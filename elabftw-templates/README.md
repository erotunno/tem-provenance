# eLabFTW templates

These three JSON files contain only the structured custom-field definitions. Create each template in your eLabFTW instance, paste the corresponding JSON into the **JSON** editor of that template, and save. Copy the optional rich-text defaults below into the template body if desired. Resource and experiment IDs are assigned by your instance.

| File | eLabFTW template kind | When to use |
| --- | --- | --- |
| [sample-v2.json](sample-v2.json) | Resource | Create one sample record when a specimen enters the lab. |
| [experiment-session.json](experiment-session.json) | Experiment | Create a session at the start of a TEM measurement and choose the Sample and Microscope in the resource-link fields. |
| [microscope.json](microscope.json) | Resource | Create an inventory record once per microscope. Verify hardware defaults before using it. |

Keep the custom-field names in the JSON so the exporter can resolve them. Leave the session body blank for free annotations, and capture the measurement goal in `experiment_description`. Enter the original ID supplied by the owner in the sample's `identifier` field. The exporter adds the specimen's persistent eLabFTW ID separately. Keep group IDs consecutive in display order for older eLabFTW views.

## Optional resource notebook bodies

### Sample

```html
<p style="line-height:1;">Record information supplied by the sample owner at handover. Name the source where useful and mark any missing or uncertain details.</p>
<h2>Material and origin</h2>
<p><em>Record what the owner says the specimen is, how it was made or where it came from, and any batch or reference details they provided.</em></p>
<h2>Preparation and prior treatment</h2>
<p><em>Summarize any processing, cleaning, coatings, or previous measurements the owner reports. Note when and by whom, if known.</em></p>
<h2>Handling and storage</h2>
<p><em>Record the owner's handling instructions, storage conditions, sensitivities, and any safety information they provided.</em></p>
<h2>Measurement request and known limitations</h2>
<p><em>Record what the owner wants to learn, any areas of interest, and any stated constraints or uncertainties.</em></p>
```

### Microscope

```html
<h2>Instrument:</h2>
<p>&nbsp;</p>
<h2>Description:</h2>
<p>&nbsp;</p>
<h2>Location:</h2>
<p>&nbsp;</p>
<h2>Manager:</h2>
```

[eLabFTW custom-field documentation](https://doc.elabftw.net/docs/usage/user-guide/custom-fields/)
