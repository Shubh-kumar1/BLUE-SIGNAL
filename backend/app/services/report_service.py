from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from app.models.vote import Vote


def create_post(db: Session, user_id: int, title: str, description: str, media_url: str | None,
               latitude: float | None, longitude: float | None, location_name: str | None) -> Post:
    post = Post(user_id=user_id, title=title, description=description, media_url=media_url,
                latitude=latitude, longitude=longitude, location_name=location_name)
    db.add(post)
    db.flush()
    return post


def create_report(db: Session, post: Post, user_id: int, urgency: str, flood_type: str,
                  confidence: float, summary: str, latitude: float | None, longitude: float | None,
                  location_name: str | None) -> Report:
    report = Report(post_id=post.id, user_id=user_id, urgency_level=urgency,
                    flood_type=flood_type, confidence_score=confidence, verified=True,
                    ai_summary=summary, latitude=latitude, longitude=longitude,
                    location_name=location_name)
    db.add(report)
    db.flush()
    return report


def posts_with_votes(db: Session) -> list[dict]:
    rows = db.execute(
        select(
            Post, User.username, User.authenticity_score,
            func.coalesce(func.sum(case((Vote.vote_type == "up", 1), else_=0)), 0).label("upvotes"),
            func.coalesce(func.sum(case((Vote.vote_type == "down", 1), else_=0)), 0).label("downvotes"),
        ).join(User, User.id == Post.user_id)
         .outerjoin(Vote, Vote.post_id == Post.id)
         .group_by(Post.id, User.username, User.authenticity_score)
         .order_by(Post.created_at.desc())
    ).all()
    output = []
    for post, username, score, upvotes, downvotes in rows:
        output.append({**post_payload(post), "username": username, "authenticity_score": score,
                       "upvotes": int(upvotes), "downvotes": int(downvotes)})
    return output


def post_payload(post: Post) -> dict:
    return {
        "id": post.id, "user_id": post.user_id, "title": post.title,
        "description": post.description, "media_url": post.media_url,
        "latitude": post.latitude, "longitude": post.longitude,
        "location_name": post.location_name, "status": post.status,
        "created_at": post.created_at,
    }


def user_posts(db: Session, user_id: int) -> list[dict]:
    posts = db.scalars(select(Post).where(Post.user_id == user_id).order_by(Post.created_at.desc())).all()
    return [{**post_payload(post), "username": post.user.username} for post in posts]


def map_reports(db: Session) -> list[dict]:
    rows = db.execute(
        select(Report, Post).join(Post, Post.id == Report.post_id).order_by(Report.created_at.desc())
    ).all()
    return [{
        "id": report.id, "post_id": report.post_id, "title": post.title,
        "description": post.description, "urgency_level": report.urgency_level,
        "flood_type": report.flood_type, "ai_summary": report.ai_summary,
        "latitude": report.latitude, "longitude": report.longitude,
        "location_name": report.location_name, "status": post.status,
    } for report, post in rows]


def all_reports(db: Session) -> list[dict]:
    rows = db.execute(
        select(Report, Post, User.username).join(Post, Post.id == Report.post_id)
        .join(User, User.id == Report.user_id).order_by(Report.created_at.desc())
    ).all()
    return [{
        "report_id": report.id, "post_id": report.post_id, "title": post.title,
        "description": post.description, "media_url": post.media_url, "status": post.status,
        "username": username, "urgency_level": report.urgency_level,
        "flood_type": report.flood_type, "confidence_score": report.confidence_score,
        "verified": report.verified, "ai_summary": report.ai_summary,
        "latitude": report.latitude, "longitude": report.longitude,
        "location_name": report.location_name, "created_at": report.created_at,
    } for report, post, username in rows]


def user_profile(db: Session, user_id: int) -> dict | None:
    user = db.get(User, user_id)
    if not user:
        return None
    profile_posts = posts_with_votes(db)
    return {
        "username": user.username, "full_name": user.full_name,
        "authenticity_score": user.authenticity_score, "created_at": user.created_at,
        "posts": [post for post in profile_posts if post["user_id"] == user_id],
    }
