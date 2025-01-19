from uuid import UUID

from sqlalchemy import Integer, func, select, update
from fastapi import HTTPException

from ... import db


async def create(quiz_id, session_id) -> UUID:
    async with db.Session() as session:
        stmt = (
            select(db.QuizQuestionOrm.id)
            .where(db.QuizQuestionOrm.quiz_id == quiz_id)
            .order_by(db.QuizQuestionOrm.order.asc())
            .limit(1)
        )
        q = await session.execute(stmt)
        first_question_id = q.scalars().first()
        if not first_question_id:
            raise HTTPException(400, "Cannot find first question for this quiz.")
        
        obj = db.GameOrm(
            quiz_id=quiz_id,
            session_id=session_id,
            current_quiz_question_id=first_question_id
        )
        session.add(obj)
        await session.commit()
        return obj.id

async def get_quiz(game_id) -> tuple[db.QuizOrm, int]:
    async with db.Session() as session:
        stmt = (
            select(db.QuizOrm)
            .select_from(db.GameOrm)
            .join(db.QuizOrm, db.QuizOrm.id == db.GameOrm.quiz_id)
            .where(db.GameOrm.id == game_id)
        )
        q = await session.execute(stmt)
        quiz = q.scalars().first()
        
        stmt = select(func.count()).select_from(db.QuizQuestionOrm).filter_by(quiz_id=quiz.id)
        q = await session.execute(stmt)
        questions_count = q.scalars().first()
        return quiz, questions_count

    
async def get_question(question_id):
    async with db.Session() as session:
        stmt = select(db.QuizQuestionOrm.text, db.QuizQuestionOrm.pic_url, db.QuizQuestionOrm.order).where(db.QuizQuestionOrm.id == question_id)
        q = await session.execute(stmt)
        question = q.mappings().first()
        
        stmt = (
            select(db.QuizQuestionAnswerOrm.text, db.QuizQuestionAnswerOrm.id)
            .where(db.QuizQuestionAnswerOrm.quiz_question_id == question_id, db.QuizQuestionAnswerOrm.is_deleted.is_not(True))
            .order_by(db.QuizQuestionAnswerOrm.order.asc())
        )
        q = await session.execute(stmt)
        answers = q.mappings().all()
        return question, answers
    
async def make_answer(game_id, question_id, answer_id) -> tuple[db.QuizQuestionAnswerOrm, db.QuizQuestionAnswerOrm]:
    chosen_answer, correct_answer = None, None
    async with db.Session() as session:
        stmt = (
            select(db.QuizQuestionAnswerOrm)
            .select_from(db.GameOrm)
            .join(db.QuizQuestionOrm, db.QuizQuestionOrm.quiz_id == db.GameOrm.quiz_id)
            .join(db.QuizQuestionAnswerOrm, db.QuizQuestionAnswerOrm.quiz_question_id == db.QuizQuestionOrm.id)
            .where(
                db.QuizQuestionAnswerOrm.id == answer_id,
                db.GameOrm.id == game_id,
                db.QuizQuestionOrm.id == question_id,
            )
        )
        q = await session.execute(stmt)
        chosen_answer: db.QuizQuestionAnswerOrm | None = q.scalars().first()
        if not chosen_answer:
            raise HTTPException(404, "Answer not found.")
        
        stmt = (
            select(db.QuizQuestionAnswerOrm)
            .where(
                db.QuizQuestionAnswerOrm.quiz_question_id == question_id,
                db.QuizQuestionAnswerOrm.points.cast(Integer) > 0
            )
        )
        q = await session.execute(stmt)
        correct_answer = q.scalars().first()
        
        session.add(db.GameAnswerOrm(
            game_id=game_id,
            quiz_question_id=question_id,
            quiz_question_answer_id=answer_id
        ))
        
        stmt = select(db.QuizQuestionOrm.quiz_id, db.QuizQuestionOrm.order).where(db.QuizQuestionOrm.id == question_id)
        q = await session.execute(stmt)
        quiz_id, current_order = q.fetchone()
        
        stmt = (
            select(db.QuizQuestionOrm.id)
            .where(
                db.QuizQuestionOrm.order > current_order,
                db.QuizQuestionOrm.quiz_id == quiz_id
            )
            .order_by(db.QuizQuestionOrm.order.asc())
            .limit(1)
        )
        q = await session.execute(stmt)
        next_question_id = q.scalars().first()
        
        if not next_question_id:
            stmt = update(db.GameOrm).where(db.GameOrm.id == game_id).values(is_finished=True, current_quiz_question_id=None)
            await session.execute(stmt)
        else:
            stmt = update(db.GameOrm).where(db.GameOrm.id == game_id).values(current_quiz_question_id=next_question_id)
            await session.execute(stmt)
        
        await session.commit()
        return chosen_answer, correct_answer


async def get_or_generate_result(game_id) -> tuple[db.QuizResultOrm, dict]:
    async with db.Session() as session:
        stmt = select(db.GameOrm.quiz_id, db.GameOrm.quiz_result_id, db.GameOrm.result).where(db.GameOrm.id == game_id)
        q = await session.execute(stmt)
        quiz_id, quiz_result_id, quiz_result_copy = q.fetchone()
        
        if quiz_result_id and quiz_result_copy:
            stmt = select(db.QuizResultOrm).where(db.QuizResultOrm.id == quiz_result_id)
            q = await session.execute(stmt)
            result = q.scalars().first()
            return result, quiz_result_copy
        
        stmt = (
            select(func.sum(db.QuizQuestionAnswerOrm.points.cast(Integer)))
            .select_from(db.GameAnswerOrm)
            .join(db.QuizQuestionAnswerOrm, db.GameAnswerOrm.quiz_question_answer_id == db.QuizQuestionAnswerOrm.id)
            .where(db.GameAnswerOrm.game_id == game_id)
        )
        q = await session.execute(stmt)
        total_points = q.scalars().first()
        
        stmt = select(func.count()).select_from(db.QuizQuestionOrm).where(db.QuizQuestionOrm.quiz_id == quiz_id)
        q = await session.execute(stmt)
        total_questions = q.scalars().first()
        
        stmt = select(db.QuizResultOrm).where(db.QuizResultOrm.quiz_id == quiz_id)
        q = await session.execute(stmt)
        results: list[db.QuizResultOrm] = q.scalars().all()
        
        for result in results:
            min_, max_ = result.points[0], result.points[0]
            if min_ <= total_points <= max_:
                break
        else:
            raise HTTPException(409, "Unable to find suitable result.")
        
        result_copy = {"points": total_points, "total_questions": total_questions}
        
        stmt = update(db.GameOrm).where(db.GameOrm.id == game_id).values(quiz_result_id=result.id, quiz_result_copy=result_copy)
        q = await session.execute(stmt)
        
        await session.commit()
        
        return result, result_copy
                
        