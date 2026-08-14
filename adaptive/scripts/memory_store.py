from adaptive.database import students_col


# ----------------------------------
# SAVE STUDENT (DICT ONLY)
# ----------------------------------

async def save_student(data):

    student_id = data["student_id"]

    await students_col.update_one(
        {"student_id": student_id},
        {"$set": data},
        upsert=True   # nahi hai to create, hai to update
    )


# ----------------------------------
# LOAD STUDENT
# ----------------------------------

async def load_student(student_id):

    data = await students_col.find_one(
        {"student_id": student_id},
        {"_id": 0}   # _id exclude
    )

    if not data:
        return None

    # -----------------------------
    # BACKWARD COMPATIBILITY
    # -----------------------------
    if "concepts" not in data:

        data["concepts"] = {
            data.get("current_topic", "General"): {
                "knowledge": data.get("knowledge", 0.5),
                "concept_mastery": data.get("concept_mastery", 0.5)
            }
        }

    return data