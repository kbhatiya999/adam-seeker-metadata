Rewrite a user's question as keyword queries for searching transcripts.

The transcripts are YouTube automatic captions of Urdu/Hindi live streams with English mixed in. They are mostly
in Devanagari, where English words are written phonetically ("वर्स" for verse, "हदीस" for hadith, "कुरान" for
Quran, "सूरह" for surah, "बुखारी" for Bukhari), and sometimes in Bengali script. Some stores hold English notes
instead. A keyword search only finds words that literally appear, so give the important words in several forms.

Return 4 to 8 short queries made of keywords, not sentences:
- English keywords
- Roman Urdu/Hindi keywords
- Devanagari keywords as they would appear in the captions, including English words written phonetically in
  Devanagari, with numbers as digits
- Bengali-script keywords, if the topic could be in a Bengali-script video
Keep names and numbers (13:2, 5686) in every query where they matter.

## Answer
JSON: {"queries": ["...", "..."]}
